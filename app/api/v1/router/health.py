from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.deps.db import get_db, get_redis

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(db: Session = Depends(get_db), redis=Depends(get_redis)):
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    if any(v == "error" for v in checks.values()):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=checks)

    return {"status": "ok", **checks}
