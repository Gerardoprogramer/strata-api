import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

REFRESH_TOKEN_PREFIX = "refresh_token:"
OAUTH_STATE_PREFIX = "oauth_state:"
OAUTH_STATE_TTL = 300  # 5 minutos


class TokenService:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    # ------------------------------------------------------------------ #
    #  Refresh token allow-list                                            #
    #  Guardamos el jti (token completo hasheado) para poder revocar       #
    # ------------------------------------------------------------------ #

    async def store_refresh_token(self, user_id: str, token: str) -> None:
        key = f"{REFRESH_TOKEN_PREFIX}{user_id}:{_short_hash(token)}"
        ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        await self.redis.setex(key, ttl, "1")

    async def is_refresh_token_valid(self, user_id: str, token: str) -> bool:
        key = f"{REFRESH_TOKEN_PREFIX}{user_id}:{_short_hash(token)}"
        return bool(await self.redis.exists(key))

    async def revoke_refresh_token(self, user_id: str, token: str) -> None:
        key = f"{REFRESH_TOKEN_PREFIX}{user_id}:{_short_hash(token)}"
        await self.redis.delete(key)

    async def revoke_all_refresh_tokens(self, user_id: str) -> None:
        """Logout de todos los dispositivos."""
        pattern = f"{REFRESH_TOKEN_PREFIX}{user_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

    # ------------------------------------------------------------------ #
    #  OAuth state — CSRF protection                                       #
    # ------------------------------------------------------------------ #

    async def store_oauth_state(self, state: str) -> None:
        key = f"{OAUTH_STATE_PREFIX}{state}"
        await self.redis.setex(key, OAUTH_STATE_TTL, "1")

    async def consume_oauth_state(self, state: str) -> bool:
        """Verifica y elimina el state en una operación atómica."""
        key = f"{OAUTH_STATE_PREFIX}{state}"
        # GETDEL: atómico, evita race condition
        result = await self.redis.getdel(key)
        return result is not None


def _short_hash(token: str) -> str:
    """Hash corto para usar como parte de la key — no guardamos el token completo."""
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()[:16]
