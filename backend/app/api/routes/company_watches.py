from __future__ import annotations

import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import CompanyWatch
from app.services.job_discovery import FETCHERS

router = APIRouter(prefix="/company-watches", tags=["company-watches"])


class CompanyWatchCreate(BaseModel):
    company_name: str
    ats_platform: str
    board_identifier: str
    enabled: bool = True


class CompanyWatchUpdate(BaseModel):
    enabled: Optional[bool] = None


class CompanyWatchResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    ats_platform: str
    board_identifier: str
    enabled: bool
    last_polled_at: Optional[str] = None
    last_poll_error: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, watch: CompanyWatch) -> "CompanyWatchResponse":
        return cls(
            id=watch.id,
            company_name=watch.company_name,
            ats_platform=watch.ats_platform,
            board_identifier=watch.board_identifier,
            enabled=watch.enabled,
            last_polled_at=watch.last_polled_at.isoformat() if watch.last_polled_at else None,
            last_poll_error=watch.last_poll_error,
        )


@router.get("", response_model=List[CompanyWatchResponse])
def list_company_watches(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[CompanyWatchResponse]:
    watches = (
        db.query(CompanyWatch)
        .filter(CompanyWatch.user_id == current_user.id)
        .order_by(CompanyWatch.company_name)
        .all()
    )
    return [CompanyWatchResponse.from_model(w) for w in watches]


@router.post("", response_model=CompanyWatchResponse, status_code=status.HTTP_201_CREATED)
def create_company_watch(
    body: CompanyWatchCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> CompanyWatchResponse:
    if body.ats_platform not in FETCHERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported ats_platform {body.ats_platform!r} - supported: {sorted(FETCHERS)}",
        )

    watch = CompanyWatch(user_id=current_user.id, **body.model_dump())
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return CompanyWatchResponse.from_model(watch)


@router.patch("/{watch_id}", response_model=CompanyWatchResponse)
def update_company_watch(
    watch_id: uuid.UUID,
    body: CompanyWatchUpdate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> CompanyWatchResponse:
    watch = db.query(CompanyWatch).filter(CompanyWatch.id == watch_id, CompanyWatch.user_id == current_user.id).first()
    if watch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company watch not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(watch, field, value)
    db.commit()
    db.refresh(watch)
    return CompanyWatchResponse.from_model(watch)


@router.delete("/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_watch(
    watch_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    watch = db.query(CompanyWatch).filter(CompanyWatch.id == watch_id, CompanyWatch.user_id == current_user.id).first()
    if watch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company watch not found")
    db.delete(watch)
    db.commit()
