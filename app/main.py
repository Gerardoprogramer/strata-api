from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routers import api_router
from app.core.config import get_settings
from app.db.redis import close_redis_pool, get_redis_pool

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_redis_pool()  # inicializa el pool al arrancar
    yield
    await close_redis_pool()  # cierra limpiamente al apagar


app = FastAPI(
    title="Strata API",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")
