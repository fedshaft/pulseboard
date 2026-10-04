from collections.abc import Generator
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_api_key, hash_session_token
from app.db.session import SessionLocal
from app.models.sessions import UserSession
from app.models.source import Source
from app.models.user import User

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_session_token(request: Request) -> str:
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    return token

def get_current_user(token: str = Depends(get_session_token), db: Session = Depends(get_db)) -> User:
    user = db.execute(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.session_id == hash_session_token(token),
            UserSession.expires_at > func.now(),
        )
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user

def get_current_source(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> Source:
    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing api key")
    source = db.execute(
        select(Source).where(Source.api_key_hash == hash_api_key(x_api_key), Source.revoked_at.is_(None))
    ).scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or revoked api key")
    return source