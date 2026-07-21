from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from .models import ApplicationData
from .services.field_mapper import FieldMapper


class BrowserState(str, Enum):
    LANDING = "landing"
    APPLY = "apply"
    LOGIN = "login"
    CREATE_ACCOUNT = "create_account"
    EMAIL_VERIFICATION = "email_verification"
    PROFILE_SETUP = "profile_setup"
    RESUME_UPLOAD = "resume_upload"
    RESUME_PARSE_WAIT = "resume_parse_wait"
    APPLICATION = "application"
    REVIEW = "review"
    SUBMIT_READY = "submit_ready"
    SUBMITTED = "submitted"
    MANUAL_INTERVENTION = "manual_intervention"
    UNKNOWN = "unknown"
    FAILED = "failed"


class PauseReason(str, Enum):
    """Values must stay string-identical to backend's app.models.BrowserPauseReason -
    queue_worker.py converts between them directly."""
    CAPTCHA = "captcha"
    MFA = "mfa"
    EMAIL_VERIFICATION = "email_verification"
    UNSUPPORTED_FLOW = "unsupported_flow"
    REPEATED_FAILURE = "repeated_failure"
    USER_REVIEW = "user_review"


# States where a resumed run should re-navigate fresh and let detect_state figure
# out where things actually are now (the site's own server-side state changed
# while paused - e.g. an account is now verified) rather than replaying old form data.
STRUCTURAL_RESUME_STATES = {
    BrowserState.LANDING,
    BrowserState.APPLY,
    BrowserState.LOGIN,
    BrowserState.CREATE_ACCOUNT,
    BrowserState.EMAIL_VERIFICATION,
    BrowserState.PROFILE_SETUP,
    BrowserState.RESUME_UPLOAD,
    BrowserState.RESUME_PARSE_WAIT,
}

# States where resuming means replaying checkpointed field values page-by-page
# before continuing, since client-side multi-page forms reset to page 1 on reload.
REPLAY_RESUME_STATES = {
    BrowserState.APPLICATION,
    BrowserState.REVIEW,
    BrowserState.SUBMIT_READY,
}


class StateHandlerResult(BaseModel):
    success: bool
    error: Optional[str] = None


@dataclass
class RunContext:
    """Carries everything the state machine loop and adapter handlers need
    across the whole run - the loop owns this, adapters read/mutate it."""

    session_id: str
    application_url: str
    application_data: ApplicationData
    user_id: str
    field_mapper: FieldMapper
    ats_platform: str = "generic"
    tenant_key: str = "default"

    unknown_streak: int = 0
    last_known_state: Optional[BrowserState] = None
    transitions: int = 0
    started_at: float = 0.0

    # Filled during APPLICATION/REVIEW pages, mirrors the old _fill_application's
    # filled_fields dict - checkpointed (redacted) and replayed on resume.
    filled_fields: dict = field(default_factory=dict)
    current_page: int = 1

    # Set once approve-submit has been called - selects whether reaching
    # SUBMIT_READY pauses for human approval (False) or proceeds to submit (True).
    approved_for_submit: bool = False

    # Populated by the APPLY-state handler after a credential-vault lookup;
    # holds {"credential_id", "email", "password", "status", "created"}.
    # Never enters filled_fields/checkpoints - login/signup handlers fill
    # email/password fields directly from here, not through FieldMapper.
    credential: Optional[dict] = None

    # Set by an application/review handler when a required field can't be
    # mapped and ApplicationQuestionAgent says it needs human input - the
    # control loop checks this after a successful handle_state call and
    # pauses with status="paused_question" instead of continuing.
    # {"label", "field_name", "question_type", "risk_level"}
    pending_question: Optional[dict] = None

    # Populated on resume when task_metadata["step"] == "question_answered" -
    # {"field_name", "answer_text"} - lets the same field-fill pass that
    # raised pending_question fill it directly instead of asking again.
    answered_question: Optional[dict] = None

    # Per-run cache of durable field_mappings lookups, keyed by form_fingerprint,
    # so a multi-page form only does one lookup per page, not one per field.
    learned_mappings_cache: dict = field(default_factory=dict)

    confirmation_id: Optional[str] = None
    started_wall_clock: datetime = field(default_factory=datetime.utcnow)

    # Replay/debug trail (see services/replay_report.py) - not part of the
    # resume-critical state above, purely diagnostic. field_sources answers
    # "where did this value come from" per field
    # ("learned_mapping"/"regex"/"answered_question"/"agent"); action_log is
    # a running list of high-level actions taken this run, in order. Both
    # accumulate for the life of the run and get attached to every
    # checkpoint - a real failure on step 17 of 25 is then replayable from
    # that checkpoint's own snapshot, not just the state name.
    field_sources: dict = field(default_factory=dict)
    action_log: list = field(default_factory=list)

    def log_action(self, action: str, **details) -> None:
        self.action_log.append({"action": action, **details})
