import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()
password_hash = PasswordHash.recommended()


# ------------------------------------------------------------------ #
#  Passwords                                                           #
# ------------------------------------------------------------------ #


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


# ------------------------------------------------------------------ #
#  Token payload schema                                                #
# ------------------------------------------------------------------ #


class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: int


# ------------------------------------------------------------------ #
#  Token creation                                                      #
# ------------------------------------------------------------------ #


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(
        payload,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(subject: uuid.UUID | str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _encode({"sub": str(subject), "exp": expire, "type": "access"})


def create_refresh_token(subject: uuid.UUID | str) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode({"sub": str(subject), "exp": expire, "type": "refresh"})


# ------------------------------------------------------------------ #
#  Token decoding                                                      #
# ------------------------------------------------------------------ #


def decode_token(token: str) -> TokenPayload:
    """
    Decodifica y valida estructura del token.
    Lanza ExpiredSignatureError o InvalidTokenError — el caller decide el HTTP status.
    """
    raw = jwt.decode(
        token,
        settings.JWT_SECRET.get_secret_value(),
        algorithms=[settings.JWT_ALGORITHM],
    )
    return TokenPayload.model_validate(raw)
