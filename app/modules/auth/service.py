from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


class AuthService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)

    def register(self, data: UserCreate) -> User:
        if self.users.get_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

        if self.users.get_by_username(data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

        user = User(
            email=data.email,
            username=data.username,
            hashed_password=hash_password(data.password),
        )
        return self.users.create(user)

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email(email)

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        return create_access_token(user.id)
