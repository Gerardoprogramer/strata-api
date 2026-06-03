from collections.abc import Generator

import redis.asyncio as aioredis
from sqlalchemy.orm import Session

from app.db.redis import get_redis_pool
from app.db.session import SessionLocal


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> aioredis.Redis:
    return get_redis_pool()
