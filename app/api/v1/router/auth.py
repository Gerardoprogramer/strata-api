import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.v1.deps.auth import get_current_user
from app.api.v1.deps.db import get_db, get_redis
from app.integrations.google.oauth import (
    build_google_redirect_url,
    exchange_code_for_token,
    generate_oauth_state,
    get_google_user_info,
)
from app.modules.auth.schemas import LoginRequest, RefreshRequest, TokenResponse
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserRead
from app.services.token_service import TokenService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service(
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> AuthService:
    return AuthService(db, redis)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, service: AuthService = Depends(get_auth_service)):
    return service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthService = Depends(get_auth_service)):
    return await service.login(data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest, service: AuthService = Depends(get_auth_service)
):
    return await service.refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: RefreshRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    await service.logout(str(current_user.id), data.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    await service.logout_all(str(current_user.id))


@router.get("/google", summary="Inicia flujo OAuth con Google")
async def google_login(redis: aioredis.Redis = Depends(get_redis)):
    state = generate_oauth_state()
    await TokenService(redis).store_oauth_state(state)
    return RedirectResponse(build_google_redirect_url(state))


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    service: AuthService = Depends(get_auth_service),
    redis: aioredis.Redis = Depends(get_redis),
):
    if not await TokenService(redis).consume_oauth_state(state):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired OAuth state"
        )

    try:
        token_data = await exchange_code_for_token(code)
        google_user = await get_google_user_info(token_data["access_token"])
    except Exception as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Google authentication failed"
        ) from err

    return await service.oauth_login_or_register(google_user)
