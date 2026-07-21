from __future__ import annotations

import uuid
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.application_question_agent import ApplicationQuestionAgent
from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import (
    Application,
    ApplicationAnswer,
    ApplicationAnswerSource,
    ApplicationQuestion,
    CanonicalJob,
    ReusableAnswer,
)
from app.schemas.application_qa import (
    GenerateQuestionsRequest,
    QuestionWithAnswer,
    ReusableAnswerCreateRequest,
    ReusableAnswerResponse,
    UpdateAnswerRequest,
)
from app.services.profile_fact_extraction import extract_facts_for_user

router = APIRouter(prefix="/applications", tags=["application-questions"])
answers_router = APIRouter(prefix="/answers", tags=["reusable-answers"])


# Default fallback questions used when the job posting has no extracted questions and
# the caller did not supply explicit question_texts. Covers a spread of risk tiers.
_DEFAULT_QUESTIONS = [
    "What is your full legal name?",
    "Are you legally authorized to work in this country?",
    "What are your salary expectations?",
    "Why are you interested in this role?",
    "Do you require visa sponsorship now or in the future?",
]

_HIGH_RISK_KEYWORDS = [
    "authorized", "authorization", "sponsorship", "sponsor",
    "clearance", "legally", "attest", "certify",
    # EEO/voluntary self-identification - legally protected demographic
    # categories. Confirmed as real, named fields (not hypothetical) on
    # Workday, Greenhouse, Ashby, and Lever during real-ATS validation -
    # e.g. Ashby's `eeoc_gender`/`eeoc_race`/`eeoc_veteran_status`,
    # Greenhouse's `hispanic_ethnicity`/`disability_status`, Lever's
    # `eeo[veteran]`/`eeo[disability]`. Must never be guessed.
    "race", "ethnicity", "gender", "veteran", "disability",
    "self-identif", "self identif", "eeo", "hispanic or latino",
]
_MEDIUM_RISK_KEYWORDS = [
    "salary", "compensation", "relocat", "years", "experience",
]
_LOW_RISK_KEYWORDS = [
    "name", "contact", "email", "phone", "education", "degree", "school",
]


def _infer_risk_level(question_text: str) -> str:
    """Infer risk tier per spec 5.8: work-auth/sponsorship/clearance/legal -> high,
    salary/relocation/years-experience -> medium, name/contact/education -> low."""
    lowered = question_text.lower()
    if any(keyword in lowered for keyword in _HIGH_RISK_KEYWORDS):
        return "high"
    if any(keyword in lowered for keyword in _MEDIUM_RISK_KEYWORDS):
        return "medium"
    if any(keyword in lowered for keyword in _LOW_RISK_KEYWORDS):
        return "low"
    return "medium"


def _infer_question_type(question_text: str) -> str:
    """Best-effort keyword-based question type inference."""
    lowered = question_text.lower()
    if any(k in lowered for k in ("race", "ethnicity", "gender", "veteran", "disability", "self-identif", "self identif")):
        return "demographic_self_id"
    if "salary" in lowered or "compensation" in lowered:
        return "salary_expectation"
    if "sponsor" in lowered or "authoriz" in lowered or "visa" in lowered:
        return "work_authorization"
    if "clearance" in lowered:
        return "security_clearance"
    if "relocat" in lowered:
        return "relocation"
    if "years" in lowered and "experience" in lowered:
        return "years_of_experience"
    if "why" in lowered and "interest" in lowered:
        return "motivation"
    if "name" in lowered:
        return "personal_info"
    if "education" in lowered or "degree" in lowered:
        return "education"
    if "contact" in lowered or "email" in lowered or "phone" in lowered:
        return "contact_info"
    return "general"


def _extract_question_texts(job: Optional[CanonicalJob]) -> List[str]:
    """Derive question texts from a job's extracted_data, falling back to defaults."""
    if job is not None:
        extracted_data = job.extracted_data or {}
        raw_questions = extracted_data.get("questions")
        if isinstance(raw_questions, list) and raw_questions:
            texts: List[str] = []
            for item in raw_questions:
                if isinstance(item, str) and item.strip():
                    texts.append(item.strip())
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("question")
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())
            if texts:
                return texts
    return list(_DEFAULT_QUESTIONS)


def _answer_to_dict(answer: Optional[ApplicationAnswer]) -> Optional[Dict[str, Any]]:
    if answer is None:
        return None
    return {
        "answer_text": answer.answer_text,
        "source": answer.source,
        "approved": answer.approved,
    }


def _to_question_with_answer(question: ApplicationQuestion) -> QuestionWithAnswer:
    return QuestionWithAnswer(
        id=question.id,
        question_text=question.question_text,
        question_type=question.question_type,
        risk_level=question.risk_level,
        answer=_answer_to_dict(question.answer),
    )


def _get_owned_application(db: Session, application_id: uuid.UUID, user_id: uuid.UUID) -> Application:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == user_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.post("/{application_id}/generate", response_model=List[QuestionWithAnswer])
async def generate_questions(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    payload: GenerateQuestionsRequest = Body(default_factory=GenerateQuestionsRequest),
) -> List[QuestionWithAnswer]:
    """Generate application questions (if needed) and answers for an application."""
    application = _get_owned_application(db, application_id, current_user.id)
    job = db.query(CanonicalJob).filter(CanonicalJob.id == application.job_id).first()

    if payload.question_texts:
        question_texts = [text for text in payload.question_texts if text and text.strip()]
    else:
        question_texts = _extract_question_texts(job)

    # Create ApplicationQuestion rows.
    questions: List[ApplicationQuestion] = []
    for text in question_texts:
        question = ApplicationQuestion(
            application_id=application.id,
            question_text=text,
            question_type=_infer_question_type(text),
            risk_level=_infer_risk_level(text),
        )
        db.add(question)
        questions.append(question)
    db.flush()

    # Gather profile facts and reusable answers for the user.
    profile_facts = extract_facts_for_user(db, current_user.id)
    reusable_answers = db.query(ReusableAnswer).filter(ReusableAnswer.user_id == current_user.id).all()

    agent = ApplicationQuestionAgent()

    for question in questions:
        result = await agent.generate_answer(
            question_text=question.question_text,
            question_type=question.question_type,
            risk_level=question.risk_level,
            profile_facts=profile_facts,
            reusable_answers=reusable_answers,
            user_id=str(current_user.id),
        )

        answer = ApplicationAnswer(
            application_question_id=question.id,
            answer_text=result["answer_text"],
            source=result["source"],
            approved=result["approved"],
        )
        db.add(answer)
        db.flush()

        for source_fact in result.get("source_facts", []):
            profile_fact_id = source_fact.get("profile_fact_id")
            db.add(
                ApplicationAnswerSource(
                    application_answer_id=answer.id,
                    profile_fact_id=uuid.UUID(profile_fact_id) if profile_fact_id else None,
                    explanation=source_fact.get("explanation"),
                )
            )
        question.answer = answer

    db.commit()

    for question in questions:
        db.refresh(question)
        if question.answer is not None:
            db.refresh(question.answer)

    return [_to_question_with_answer(question) for question in questions]


@router.get("/{application_id}/questions", response_model=List[QuestionWithAnswer])
def get_questions(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> List[QuestionWithAnswer]:
    """Get all questions (with their answers) for an application."""
    _get_owned_application(db, application_id, current_user.id)

    questions = (
        db.query(ApplicationQuestion)
        .filter(ApplicationQuestion.application_id == application_id)
        .order_by(ApplicationQuestion.created_at.asc())
        .all()
    )
    return [_to_question_with_answer(question) for question in questions]


@router.patch("/{application_id}/questions/{question_id}", response_model=QuestionWithAnswer)
def update_answer(
    application_id: uuid.UUID,
    question_id: uuid.UUID,
    update_data: UpdateAnswerRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> QuestionWithAnswer:
    """Manually update (or create) the answer for an application question."""
    _get_owned_application(db, application_id, current_user.id)

    question = (
        db.query(ApplicationQuestion)
        .filter(
            ApplicationQuestion.id == question_id,
            ApplicationQuestion.application_id == application_id,
        )
        .first()
    )
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    answer = question.answer
    if answer is None:
        answer = ApplicationAnswer(
            application_question_id=question.id,
            answer_text=update_data.answer_text,
            source="user_input",
            approved=True,
        )
        db.add(answer)
    else:
        answer.answer_text = update_data.answer_text
        answer.source = "user_input"
        answer.approved = True

    db.commit()
    db.refresh(question)
    db.refresh(question.answer)
    return _to_question_with_answer(question)


@answers_router.post("", response_model=ReusableAnswerResponse, status_code=status.HTTP_201_CREATED)
def create_reusable_answer(
    answer_in: ReusableAnswerCreateRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ReusableAnswer:
    """Create a new reusable answer for the current user."""
    answer = ReusableAnswer(
        user_id=current_user.id,
        canonical_question=answer_in.canonical_question,
        semantic_variants=answer_in.semantic_variants,
        exact_answer=answer_in.exact_answer,
        allowed_paraphrasing=answer_in.allowed_paraphrasing,
        risk_level=answer_in.risk_level,
        categories=answer_in.categories,
        expiration_date=answer_in.expiration_date,
        user_approved=answer_in.user_approved,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


@answers_router.post("/{answer_id}/approve", response_model=ReusableAnswerResponse)
def approve_reusable_answer(
    answer_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ReusableAnswer:
    """Mark a reusable answer as user-approved."""
    answer = (
        db.query(ReusableAnswer)
        .filter(ReusableAnswer.id == answer_id, ReusableAnswer.user_id == current_user.id)
        .first()
    )
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reusable answer not found")

    answer.user_approved = True
    db.commit()
    db.refresh(answer)
    return answer
