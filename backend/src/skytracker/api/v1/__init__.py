from fastapi import APIRouter

from . import (
    admin,
    auth,
    compare,
    events,
    feedback,
    health,
    jobs_api,
    meta,
    moving,
    objects,
    resolve,
    sky,
    suggest,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(meta.router)
router.include_router(events.router)
router.include_router(resolve.router)
router.include_router(sky.router)
router.include_router(jobs_api.router)
router.include_router(objects.router)
router.include_router(compare.router)
router.include_router(moving.router)
router.include_router(feedback.router)
router.include_router(suggest.router)
router.include_router(auth.router)
router.include_router(admin.router)
