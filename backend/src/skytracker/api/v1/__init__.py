from fastapi import APIRouter

from . import events, health, jobs_api, meta, objects, resolve, sky

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(meta.router)
router.include_router(events.router)
router.include_router(resolve.router)
router.include_router(sky.router)
router.include_router(jobs_api.router)
router.include_router(objects.router)
