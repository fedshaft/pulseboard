from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db, require_admin
from app.core.security import API_KEY_DISPLAY_CHARS, generate_api_key, hash_api_key
from app.models.source import Source
from app.models.user import User
from app.schemas.source import SourceCreate, SourceCreated, SourceOut

router = APIRouter(prefix="/sources", tags=["sources"])

@router.post("", response_model=SourceCreated, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> SourceCreated:
    api_key = generate_api_key()
    source = Source(
        name=payload.name,
        api_key_hash=hash_api_key(api_key),
        key_prefix=api_key[:API_KEY_DISPLAY_CHARS],
        created_by=admin.id,
    )
    db.add(source)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source name already exists")

    db.refresh(source)
    return SourceCreated(**SourceOut.model_validate(source).model_dump(), api_key=api_key)

@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Source]:
    return list(db.execute(select(Source).order_by(Source.id)).scalars())

@router.get("/{source_id}", response_model=SourceOut)
def get_source(source_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source

@router.post("/{source_id}/revoke", response_model=SourceOut)
def revoke_source(source_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    if source.revoked_at is None:
        source.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(source)
    return source
