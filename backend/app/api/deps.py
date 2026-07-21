from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """Get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_internal_api_key(x_internal_api_key: Annotated[Optional[str], Header()] = None) -> None:
    """Gate for service-to-service routes (e.g. the ATS credential vault).

    `api`'s port is published to the host (docker-compose.yml), so these
    routes are reachable outside the Docker network too - this is not
    optional defense-in-depth, it's the only thing stopping a regular
    authenticated user (or anyone on the host) from calling an endpoint that
    returns plaintext third-party account passwords.
    """
    if not x_internal_api_key or x_internal_api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal API key")


RequireInternalApiKey = Depends(require_internal_api_key)
