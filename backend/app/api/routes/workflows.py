from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import WorkflowTask
from app.schemas.workflow import WorkflowTask as WorkflowTaskSchema

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowTaskSchema])
def list_workflows(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 100
) -> list[WorkflowTask]:
    """List all workflow tasks."""
    workflows = db.query(WorkflowTask).order_by(
        WorkflowTask.created_at.desc()
    ).offset(skip).limit(limit).all()
    return workflows


@router.get("/{workflow_id}", response_model=WorkflowTaskSchema)
def get_workflow(
    workflow_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> WorkflowTask:
    """Get a specific workflow task."""
    workflow = db.query(WorkflowTask).filter(WorkflowTask.id == workflow_id).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    return workflow
