import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

API_KEY_PREFIX = "sk_live_"


def generate_api_key() -> tuple[str, str]:
    """Returns (raw_key, display_prefix). Only the hash of raw_key is ever persisted."""
    raw_key = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return raw_key, raw_key[:12]


def hash_api_key(raw_key: str) -> str:
    return pwd_context.hash(raw_key)


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    return pwd_context.verify(raw_key, key_hash)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: uuid.UUID, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": str(subject), "exp": expire, "type": "user"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_worker_token(worker_id: uuid.UUID, project_id: uuid.UUID) -> str:
    """Worker tokens don't expire on their own timeline; a worker is expected to re-register
    on restart. Revocation happens by marking the Worker row offline server-side."""
    payload = {
        "sub": str(worker_id),
        "project_id": str(project_id),
        "type": "worker",
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
