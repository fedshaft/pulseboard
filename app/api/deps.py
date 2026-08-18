from collections.abc import Generator
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_session_token
from app.db.session import SessionLocal
from app.models.sessions import UserSession
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
