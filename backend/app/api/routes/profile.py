from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import Profile
from app.schemas import ProfileCreate, ProfileUpdate
from app.schemas.profile import Profile as ProfileSchema

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileSchema)
def get_profile(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> Profile:
    """Get current user profile."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return profile


@router.put("", response_model=ProfileSchema)
def update_profile(
    profile_in: ProfileUpdate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> Profile:
    """Update current user profile."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    
    if not profile:
        # Create profile if it doesn't exist
        profile = Profile(user_id=current_user.id)
        db.add(profile)
    
    # Update fields
    update_data = profile_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    return profile
