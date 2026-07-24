from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.application_question_agent import ApplicationQuestionAgent
from app.api.deps import RequireInternalApiKey
from app.api.routes.application_questions import _infer_question_type, _infer_risk_level
from app.core.database import get_db
from app.models import ReusableAnswer
from app.services.profile_fact_extraction import extract_facts_for_user

router = APIRouter(
    prefix="/internal/dynamic-questions",
    tags=["internal"],
    dependencies=[RequireInternalApiKey],
)


class AnswerQuestionRequest(BaseModel):
    user_id: str
    question_text: str
    question_type: str = ""
    risk_level: str = ""
    expects_short_answer: bool = False


@router.post("/answer")
async def answer_question(
    body: AnswerQuestionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Answer a field browser-worker couldn't map, using the exact same
    precedence/truthfulness pipeline (ApplicationQuestionAgent) already used
    for pre-application Q&A - reusing verified profile facts and the approved
    reusable-answer bank, never fabricating an answer to a high-risk question.
    Called only by browser-worker over the internal network.
    """
    question_type = body.question_type or _infer_question_type(body.question_text)
    risk_level = body.risk_level or _infer_risk_level(body.question_text)

    profile_facts = extract_facts_for_user(db, body.user_id)
    reusable_answers = db.query(ReusableAnswer).filter(ReusableAnswer.user_id == body.user_id).all()

    agent = ApplicationQuestionAgent()
    result = await agent.generate_answer(
        question_text=body.question_text,
        question_type=question_type,
        risk_level=risk_level,
        profile_facts=profile_facts,
        reusable_answers=reusable_answers,
        user_id=body.user_id,
        expects_short_answer=body.expects_short_answer,
    )
    result["question_type"] = question_type
    result["risk_level"] = risk_level
    return result
