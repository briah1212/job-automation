from __future__ import annotations

import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import SearchProfile
from app.schemas.search_profile import (
    SearchProfile as SearchProfileSchema,
    SearchProfileCreate,
    SearchProfileUpdate,
)

router = APIRouter(prefix="/search-profiles", tags=["search-profiles"])


@router.post("", response_model=SearchProfileSchema, status_code=status.HTTP_201_CREATED)
def create_search_profile(
    profile_data: SearchProfileCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> SearchProfile:
    """Create a new search profile."""
    profile = SearchProfile(
        user_id=current_user.id,
        **profile_data.model_dump()
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=List[SearchProfileSchema])
def list_search_profiles(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    enabled_only: bool = False
) -> List[SearchProfile]:
    """List all search profiles for current user."""
    query = db.query(SearchProfile).filter(SearchProfile.user_id == current_user.id)
    
    if enabled_only:
        query = query.filter(SearchProfile.enabled == True)
    
    profiles = query.order_by(SearchProfile.created_at.desc()).all()
    return profiles


@router.get("/{profile_id}", response_model=SearchProfileSchema)
def get_search_profile(
    profile_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> SearchProfile:
    """Get a specific search profile."""
    profile = db.query(SearchProfile).filter(
        SearchProfile.id == profile_id,
        SearchProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search profile not found"
        )
    
    return profile


@router.patch("/{profile_id}", response_model=SearchProfileSchema)
def update_search_profile(
    profile_id: uuid.UUID,
    profile_data: SearchProfileUpdate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> SearchProfile:
    """Update a search profile."""
    profile = db.query(SearchProfile).filter(
        SearchProfile.id == profile_id,
        SearchProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search profile not found"
        )
    
    # Update only provided fields
    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search_profile(
    profile_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
):
    """Delete a search profile."""
    profile = db.query(SearchProfile).filter(
        SearchProfile.id == profile_id,
        SearchProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search profile not found"
        )
    
    db.delete(profile)
    db.commit()
