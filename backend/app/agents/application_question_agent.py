from __future__ import annotations

from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.ai_gateway.gateway import AIGateway
from app.models import ProfileFact, ReusableAnswer
from app.services.experience_calculator import calculate_years_of_experience
from app.services.reusable_answer_matching import find_matching_reusable_answer

# Confirmed live against a real Jobvite posting (NinjaOne): the AI-generated
# path's own prompt instructs "If the facts do not contain enough
# information to answer, say so briefly" - the model followed that
# instruction correctly, but nothing here ever checked WHETHER it did
# before returning needs_user_input=False unconditionally. The literal
# disclaimer prose ("The provided facts do not include any information
# about a city.") was then typed straight into the real "City" field as if
# it were a genuine answer - not a hypothetical, this happened on a real
# live application. Any answer matching one of these phrases is treated as
# "the AI couldn't actually answer" and escalated to needs_user_input
# instead. Deliberately phrase-based, not a single word like "no" (a
# legitimate one-word answer to a yes/no question), and covers this
# constructions the current prompt's own wording ("say so") tends to
# produce, not every conceivable refusal phrasing.
_UNABLE_TO_ANSWER_PHRASES = (
    "do not contain", "does not contain", "don't contain",
    "do not include", "does not include", "don't include",
    "not enough information", "insufficient information",
    "no information about", "no information regarding",
    "cannot determine", "can't determine", "unable to determine",
    "i don't have", "i do not have", "not specified in",
    "not provided in the", "not mentioned in the",
)


def _looks_like_unable_to_answer(answer_text: str) -> bool:
    lowered = answer_text.lower()
    return any(phrase in lowered for phrase in _UNABLE_TO_ANSWER_PHRASES)


# Best-effort keyword list used to guess which skill a "years of experience" question
# is asking about. Not exhaustive - falls back to matching any experience_bullet.
_KNOWN_SKILLS = [
    "python", "java", "javascript", "typescript", "sql", "react", "node",
    "aws", "azure", "gcp", "kubernetes", "docker", "go", "golang", "c++",
    "c#", "ruby", "php", "rust", "scala", "swift", "kotlin", "django",
    "flask", "fastapi", "spring", "postgresql", "mysql", "mongodb",
    "machine learning", "data science", "devops", "product management",
    "project management", "sales", "marketing", "management",
]


class ApplicationQuestionAgent(BaseAgent):
    """Agent for generating answers to application form questions.

    Implements the precedence order from spec 13.2: exact reusable-answer match,
    then the high-risk hard rule (never guess), then deterministic calculation
    (e.g. years of experience), then AI generation grounded strictly in verified
    profile facts.
    """

    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute agent logic (sync wrapper is not used - callers should await generate_answer)."""
        raise NotImplementedError(
            "ApplicationQuestionAgent is async-only; call generate_answer() directly."
        )

    async def generate_answer(
        self,
        question_text: str,
        question_type: str,
        risk_level: str,
        profile_facts: List[ProfileFact],
        reusable_answers: List[ReusableAnswer],
        user_id: str,
        expects_short_answer: bool = False,
    ) -> Dict[str, Any]:
        """Generate an answer for a single application question, following precedence order."""

        # (1) Exact/canonical reusable-answer match.
        match = find_matching_reusable_answer(question_text, reusable_answers)
        if match is not None:
            return {
                "answer_text": match.exact_answer,
                "source": "exact_approved" if match.user_approved else "canonical_approved",
                "approved": match.user_approved,
                "needs_user_input": False,
                "source_facts": [],
            }

        # (2) Hard rule: never guess high-risk answers.
        if risk_level == "high":
            return {
                "answer_text": "",
                "source": "user_input",
                "approved": False,
                "needs_user_input": True,
                "source_facts": [],
            }

        # (3) Deterministic years-of-experience calculation.
        lowered_question = question_text.lower()
        if "years" in lowered_question and "experience" in lowered_question:
            skill = self._guess_skill(lowered_question)
            calc_result = calculate_years_of_experience(profile_facts, skill)
            if calc_result["years"] is not None:
                source_facts = [
                    {
                        "profile_fact_id": entry["fact_id"],
                        "explanation": f"Used to compute years of experience (matched range: {entry['extracted_range']})",
                    }
                    for entry in calc_result["calculation_basis"]
                ]
                return {
                    "answer_text": f"{calc_result['years']} years",
                    "source": "deterministic",
                    "approved": False,
                    "needs_user_input": False,
                    "source_facts": source_facts,
                }
            # Falls through to (4) for low/medium risk when no years value could be derived.

        # (4) AI-generated answer grounded strictly in verified profile facts.
        facts_used = profile_facts
        facts_block = "\n".join(f"- {fact.content}" for fact in facts_used) or "(no verified facts available)"

        # Confirmed live against a real Pinpoint posting (Confluence
        # Technologies): a field labeled "Town" reached this path (no
        # FieldMapper rule covered it) and the blanket "1-3 sentences"
        # instruction produced a full personal-summary-style answer
        # ("Brian Hsu, email hsubrian1212@gmail.com, phone 646-236-7795,
        # LinkedIn...") for what needed to be a single town/city name.
        # expects_short_answer (field.input_type != "textarea", set by the
        # caller) tells the model this is a single-line field expecting a
        # short value, not an open-ended question inviting prose.
        length_instruction = (
            "Keep the answer to a short phrase or single value (a few words at most) "
            "suitable for a single-line text field - not a full sentence."
            if expects_short_answer
            else "Keep the answer concise (1-3 sentences)."
        )
        prompt = (
            "You are helping a job applicant answer a job application question.\n"
            "Answer ONLY using the verified facts listed below. Never invent, assume, "
            "or embellish information that is not present in these facts. If the facts "
            "do not contain enough information to answer, say so briefly.\n"
            f"{length_instruction}\n\n"
            f"Question: {question_text}\n\n"
            f"Verified facts:\n{facts_block}\n\n"
            "Answer:"
        )

        gateway = AIGateway()
        answer_text = await gateway.generate_text(
            prompt=prompt, agent_type="application_question", user_id=user_id
        )
        answer_text = answer_text.strip() if isinstance(answer_text, str) else answer_text

        source_facts = [
            {
                "profile_fact_id": str(fact.id) if fact.id else None,
                "explanation": "Consulted as verified profile fact for AI-generated answer",
            }
            for fact in facts_used
        ]

        # The prompt above explicitly tells the model to say so when it
        # can't answer from the given facts - that's the correct, honest
        # response, but it's prose meant for a human reviewer, not a
        # literal value to type into the actual field. See
        # _looks_like_unable_to_answer's docstring for how this was found.
        if not answer_text or _looks_like_unable_to_answer(answer_text):
            return {
                "answer_text": "",
                "source": "ai_generated",
                "approved": False,
                "needs_user_input": True,
                "source_facts": source_facts,
            }

        return {
            "answer_text": answer_text,
            "source": "ai_generated",
            "approved": False,
            "needs_user_input": False,
            "source_facts": source_facts,
        }

    @staticmethod
    def _guess_skill(lowered_question: str) -> str:
        """Best-effort guess of which skill a years-of-experience question refers to."""
        for skill in _KNOWN_SKILLS:
            if skill in lowered_question:
                return skill
        return ""
