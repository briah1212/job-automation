import hashlib
import logging
from typing import List, Optional

from ..models import FormField
from ..state import RunContext
from .dynamic_questions_client import DynamicQuestionsError, answer_question
from .field_mapping_client import lookup_mappings, record_mapping

logger = logging.getLogger(__name__)

_YES_HINTS = ("yes", "willing", "able", "can ", "sure", "happy to", "would")
_NO_HINTS = ("no", "not willing", "unable", "cannot", "can't", "wouldn't")


def compute_form_fingerprint(field_names: List[str]) -> str:
    """A stable identifier for a form's shape - same field names in any order
    produce the same fingerprint, so a learned mapping applies to every future
    encounter with this exact form, per spec 14.3 ("Store learned mappings by:
    Domain, ATS, Form fingerprint, Label pattern")."""
    normalized = ",".join(sorted(field_names))
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _constrain_to_options(raw_answer: str, field: FormField) -> Optional[str]:
    """Map a free-text answer onto one of a select field's actual option
    values. An AI-generated (or human-typed) answer like "Yes, I'd be happy
    to relocate" can't be handed to Playwright's select_option() directly -
    it has to be exactly one of the option strings the site defines, which
    the answer's author (agent or human) has no way of knowing in advance.

    Returns None if no confident match can be made - the caller must not
    silently fill an unmatched value into a constrained-choice field.
    """
    if field.input_type != "select" or not field.options:
        return raw_answer

    lowered = raw_answer.strip().lower()
    normalized = lowered.replace("_", " ").replace("-", " ")

    for option in field.options:
        if option.lower() == lowered:
            return option
    for option in field.options:
        option_lower = option.lower()
        if option_lower in lowered or option_lower.replace("_", " ").replace("-", " ") in normalized:
            return option

    yes_options = [o for o in field.options if o.lower() in ("yes", "true", "y")]
    no_options = [o for o in field.options if o.lower() in ("no", "false", "n")]
    if yes_options and any(hint in lowered for hint in _YES_HINTS):
        return yes_options[0]
    if no_options and any(hint in lowered for hint in _NO_HINTS):
        return no_options[0]

    return None


async def _get_learned_mappings(ctx: RunContext, form_fingerprint: str) -> dict:
    if form_fingerprint not in ctx.learned_mappings_cache:
        ctx.learned_mappings_cache[form_fingerprint] = await lookup_mappings(
            ats_platform=ctx.ats_platform, domain=ctx.tenant_key, form_fingerprint=form_fingerprint
        )
    return ctx.learned_mappings_cache[form_fingerprint]


async def resolve_field_value(field: FormField, ctx: RunContext, app_data_dict: dict, form_fingerprint: str = ""):
    """Shared field-value resolution used by every adapter's application/review
    handler, so the field-mapping and dynamic-questions fallback logic lives
    in exactly one place instead of being duplicated per adapter.

    Order:
    1. Durable, previously-learned/reviewed mapping for this exact form shape
       (see field_mapping_client) - a human's correction always wins here,
       since record_mapping never overwrites an existing row.
    2. FieldMapper's built-in regex rules (deterministic, primary path) - a
       first-time success here is recorded as a new "learned" mapping so the
       next encounter with this form skips straight to step 1.
    3. An in-progress answer to this exact field from a just-resumed
       question-answer cycle.
    4. For required fields only, ApplicationQuestionAgent via the internal
       endpoint.

    Returns the resolved value, or None if the field should be left unfilled
    (optional and unmapped) or a question is now pending (check
    ctx.pending_question - the caller must stop filling further fields on
    this pass and let the control loop pause).
    """
    if form_fingerprint:
        learned = await _get_learned_mappings(ctx, form_fingerprint)
        canonical = learned.get(field.name)
        if canonical and canonical in app_data_dict and app_data_dict[canonical] is not None:
            constrained = _constrain_to_options(str(app_data_dict[canonical]), field)
            if constrained is not None:
                # record_mapping is an upsert - for an already-known mapping this
                # only bumps use_count/last_used_at, so "reviewable" mappings
                # accurately reflect what's actually being reused vs. learned
                # once and never hit again.
                await record_mapping(
                    ats_platform=ctx.ats_platform,
                    domain=ctx.tenant_key,
                    form_fingerprint=form_fingerprint,
                    field_name=field.name,
                    label=field.label,
                    canonical_name=canonical,
                )
                ctx.field_sources[field.name] = "learned_mapping"
                return constrained
            # A select field whose stored value doesn't match any of this
            # form's actual options (e.g. profile.work_authorization = "US
            # Citizen" against a plain Yes/No <select>) falls through to the
            # remaining resolution steps below instead of returning a value
            # that select_option() would reject outright, stalling the
            # worker on a required field until it times out.

    canonical_name = ctx.field_mapper.map_to_canonical(field)
    value = ctx.field_mapper.get_value_for_field(field, app_data_dict)
    if value is not None:
        constrained = _constrain_to_options(str(value), field)
        if constrained is not None:
            if form_fingerprint and canonical_name:
                await record_mapping(
                    ats_platform=ctx.ats_platform,
                    domain=ctx.tenant_key,
                    form_fingerprint=form_fingerprint,
                    field_name=field.name,
                    label=field.label,
                    canonical_name=canonical_name,
                )
            ctx.field_sources[field.name] = "regex"
            return constrained
        # Same fallback as above - don't return a value select_option() can't use.

    if ctx.answered_question and ctx.answered_question.get("field_name") == field.name:
        raw = str(ctx.answered_question["answer_text"])
        # The human already answered once - if it doesn't cleanly constrain
        # to an option, attempt it as-is rather than pausing on the same
        # question again (avoids a pause/answer/pause loop); fill_field's own
        # error handling and the navigation-stall detection in navigate_next
        # will surface a clear failure if it truly can't be filled.
        ctx.field_sources[field.name] = "answered_question"
        return _constrain_to_options(raw, field) or raw

    if not field.required:
        logger.warning(f"No value found for optional field: {field.name} ({field.label})")
        return None

    logger.info(f"No deterministic mapping for required field {field.name} ({field.label}) - asking ApplicationQuestionAgent")
    try:
        # Confirmed live against a real Pinpoint posting (Confluence
        # Technologies): a field labeled "Town" has no FieldMapper rule
        # (only "city" was covered, not this common synonym - see the
        # rule added alongside this fix) and fell all the way through to
        # this AI-generated path, which produced a full 1-3 sentence
        # personal-summary-style answer ("Brian Hsu, email
        # hsubrian1212@gmail.com, phone 646-236-7795, LinkedIn...") into
        # what needed to be a single town/city name. The agent's prompt
        # had no way to know this was a single-line text field expecting
        # a short value rather than an open-ended question expecting
        # prose - textarea is the one input_type on a real form that
        # actually invites a multi-sentence answer.
        answer = await answer_question(
            user_id=ctx.user_id,
            question_text=field.label,
            expects_short_answer=field.input_type != "textarea",
        )
    except DynamicQuestionsError as exc:
        logger.error(f"Dynamic question lookup failed for {field.name}: {exc}")
        ctx.pending_question = {
            "label": field.label,
            "field_name": field.name,
            "question_type": "custom",
            "risk_level": "medium",
        }
        return None

    if answer.get("needs_user_input"):
        ctx.pending_question = {
            "label": field.label,
            "field_name": field.name,
            "question_type": answer.get("question_type", "custom"),
            "risk_level": answer.get("risk_level", "medium"),
        }
        return None

    resolved = _constrain_to_options(answer.get("answer_text", ""), field)
    if resolved is None:
        logger.info(f"Agent's answer for {field.name} didn't confidently map to a select option - deferring to the user")
        ctx.pending_question = {
            "label": field.label,
            "field_name": field.name,
            "question_type": answer.get("question_type", "custom"),
            "risk_level": answer.get("risk_level", "medium"),
        }
        return None

    logger.info(f"ApplicationQuestionAgent answered {field.name} via source={answer.get('source')}")
    ctx.field_sources[field.name] = f"agent:{answer.get('source', 'unknown')}"
    return resolved
