from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session

from app.api.v1.deps.db import get_db
from app.core.security import decode_token
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except ExpiredSignatureError as err:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired") from err
    except InvalidTokenError as err:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from err

    if payload.type != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    user = UserRepository(db).get_by_id(payload.sub)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    return user


def require_verified(user: User = Depends(get_current_user)) -> User:
    if not user.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email not verified")
    return user
