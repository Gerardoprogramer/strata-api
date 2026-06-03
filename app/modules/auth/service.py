import redis.asyncio as aioredis
from fastapi import HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth.schemas import TokenResponse
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.services.token_service import TokenService


class AuthService:
    def __init__(self, db: Session, redis: aioredis.Redis):
        self.users = UserRepository(db)
        self.tokens = TokenService(redis)

    # ------------------------------------------------------------------ #
    #  Registro                                                            #
    # ------------------------------------------------------------------ #

    def register(self, data: UserCreate) -> User:
        if self.users.get_by_email(data.email):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")
        if self.users.get_by_username(data.username):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already taken")

        try:
            return self.users.create(
                User(
                    email=data.email,
                    username=data.username,
                    hashed_password=hash_password(data.password),
                )
            )
        except IntegrityError as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "User already exists"
            ) from err

    # ------------------------------------------------------------------ #
    #  Login                                                               #
    # ------------------------------------------------------------------ #

    async def login(self, email: str, password: str) -> TokenResponse:
        user = self.users.get_by_email(email)

        if not user or not user.has_password:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        if not verify_password(password, user.hashed_password):  # type: ignore[arg-type]
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

        return await self._build_token_response(user.id)

    # ------------------------------------------------------------------ #
    #  Refresh                                                             #
    # ------------------------------------------------------------------ #

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except ExpiredSignatureError as err:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Refresh token expired"
            ) from err
        except InvalidTokenError as err:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Invalid refresh token"
            ) from err

        if payload.type != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

        if not await self.tokens.is_refresh_token_valid(payload.sub, refresh_token):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked")

        user = self.users.get_by_id(payload.sub)
        if not user or not user.is_active:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "User not found or inactive"
            )

        # Rotación: invalida el anterior, emite uno nuevo
        await self.tokens.revoke_refresh_token(payload.sub, refresh_token)
        return await self._build_token_response(user.id)

    # ------------------------------------------------------------------ #
    #  Logout                                                              #
    # ------------------------------------------------------------------ #

    async def logout(self, user_id: str, refresh_token: str) -> None:
        await self.tokens.revoke_refresh_token(user_id, refresh_token)

    async def logout_all(self, user_id: str) -> None:
        await self.tokens.revoke_all_refresh_tokens(user_id)

    # ------------------------------------------------------------------ #
    #  OAuth — Google                                                      #
    # ------------------------------------------------------------------ #

    async def oauth_login_or_register(self, google_user: dict) -> TokenResponse:
        provider = "google"
        provider_id = str(google_user["sub"])

        user = self.users.get_by_oauth(provider, provider_id)

        if not user:
            user = self.users.get_by_email(google_user["email"])
            if user:
                user.oauth_provider = provider
                user.oauth_provider_id = provider_id
                user.avatar_url = google_user.get("picture")
                user.is_verified = True
                self.users.update(user)
            else:
                try:
                    user = self.users.create(
                        User(
                            email=google_user["email"],
                            username=self._unique_username(google_user),
                            oauth_provider=provider,
                            oauth_provider_id=provider_id,
                            avatar_url=google_user.get("picture"),
                            is_verified=True,
                        )
                    )
                except IntegrityError as err:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT, "User already exists"
                    ) from err

        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

        return await self._build_token_response(user.id)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    async def _build_token_response(self, user_id) -> TokenResponse:
        access = create_access_token(user_id)
        refresh = create_refresh_token(user_id)
        await self.tokens.store_refresh_token(str(user_id), refresh)
        return TokenResponse(access_token=access, refresh_token=refresh)

    def _unique_username(self, google_user: dict) -> str:
        base = (
            google_user.get("name", "").lower().replace(" ", "_")[:40]
            or google_user["email"].split("@")[0]
        )
        username, counter = base, 1
        while self.users.get_by_username(username):
            username = f"{base}_{counter}"
            counter += 1
        return username
