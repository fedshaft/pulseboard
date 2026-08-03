import hashlib
import secrets

from pwdlib import PasswordHash

pwd_context = PasswordHash.recommended()

SESSION_TOKEN_BYTES = 32

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)

def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()