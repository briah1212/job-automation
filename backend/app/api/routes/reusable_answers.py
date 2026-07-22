from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import ReusableAnswer

router = APIRouter(prefix="/reusable-answers", tags=["reusable-answers"])


class ReusableAnswerCreate(BaseModel):
    canonical_question: str
    semantic_variants: List[str] = []
    exact_answer: str
    allowed_paraphrasing: bool = False
    risk_level: str
    categories: List[str] = []
    user_approved: bool = True


class ReusableAnswerUpdate(BaseModel):
    exact_answer: Optional[str] = None
    semantic_variants: Optional[List[str]] = None
    user_approved: Optional[bool] = None


class ReusableAnswerResponse(BaseModel):
    id: uuid.UUID
    canonical_question: str
    semantic_variants: List[str]
    exact_answer: str
    allowed_paraphrasing: bool
    risk_level: str
    categories: List[str]
    user_approved: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=List[ReusableAnswerResponse])
def list_reusable_answers(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[ReusableAnswer]:
    """The user's own reusable-answer bank - what the browser worker will never
    have to ask again (see ApplicationQuestionAgent.find_matching_reusable_answer)."""
    return (
        db.query(ReusableAnswer)
        .filter(ReusableAnswer.user_id == current_user.id)
        .order_by(ReusableAnswer.canonical_question)
        .all()
    )


@router.post("", response_model=ReusableAnswerResponse, status_code=status.HTTP_201_CREATED)
def create_reusable_answer(
    body: ReusableAnswerCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ReusableAnswer:
    """Proactively teach the system an answer before any application ever asks -
    the same trust level as answering a paused question live (user_approved
    defaults True: a human is directly asserting this fact about themselves)."""
    answer = ReusableAnswer(user_id=current_user.id, **body.model_dump())
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


@router.patch("/{answer_id}", response_model=ReusableAnswerResponse)
def update_reusable_answer(
    answer_id: uuid.UUID,
    body: ReusableAnswerUpdate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ReusableAnswer:
    answer = (
        db.query(ReusableAnswer)
        .filter(ReusableAnswer.id == answer_id, ReusableAnswer.user_id == current_user.id)
        .first()
    )
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reusable answer not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(answer, field, value)
    answer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(answer)
    return answer


@router.delete("/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reusable_answer(
    answer_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    answer = (
        db.query(ReusableAnswer)
        .filter(ReusableAnswer.id == answer_id, ReusableAnswer.user_id == current_user.id)
        .first()
    )
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reusable answer not found")
    db.delete(answer)
    db.commit()
