from fastapi import APIRouter

from . import events, health, meta

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(meta.router)
router.include_router(events.router)
