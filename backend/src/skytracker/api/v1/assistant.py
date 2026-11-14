"""Assistant: POST /assistant/message starts a job whose answer streams over WebSocket as
"assistant_chunk" progress steps (topic job:<id>); the job result holds the complete answer, so HTTP
polling alone also works. GET /assistant/quick lists the quick-question buttons (from the FAQ file).

What the assistant may read is loaded here, on the server: the comparison by id (only this browser's
or the signed-in user's) or else this browser's latest one, and the cached object info. The message
text itself is not stored; the event log keeps only which kind of answer was given.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from ... import cache, jobs
from ...db import session_scope
from ...db.models import Comparison
from ...events import _user_id, log_action
from ...realtime import manager
from ...security import TokenBucket
from ...services import assistant as AS
from .objects import DAY, build_info

router = APIRouter(prefix="/assistant", tags=["assistant"])
_limiter = TokenBucket(rate_per_min=20, burst=10)
CHUNK_DELAY_S = 0.035  # pacing of the typing effect
SUBSCRIBE_WAIT_S = 1.0  # give the browser time to subscribe to the job topic before streaming


class PageObject(BaseModel):
    """Labels of the open object (used for names only; numbers come from the server)."""

    key: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=120)
    kind: str | None = Field(default=None, pattern="^(object|coordinate|solar_system)$")
    main_id: str | None = Field(default=None, max_length=100)
    designation: str | None = Field(default=None, max_length=40)
    orbit_class: str | None = Field(default=None, max_length=80)


class AssistantContext(BaseModel):
    object: PageObject | None = None
    comparison_id: str | None = Field(default=None, max_length=32, pattern=r"^[0-9a-f]{1,32}$")


class MessageRequest(BaseModel):
    message: str | None = Field(default=None, max_length=AS.MAX_MESSAGE)
    quick: str | None = Field(default=None, max_length=40)
    context: AssistantContext = Field(default_factory=AssistantContext)


def load_comparison(
    comparison_id: str | None, object_key: str | None, sid: str, uid: int | None
) -> dict | None:
    owner = Comparison.session_id == sid
    if uid is not None:
        owner = or_(owner, Comparison.user_id == uid)
    with session_scope() as db:
        q = select(Comparison).where(owner)
        if comparison_id:
            q = q.where(Comparison.id == comparison_id)
        elif object_key:
            q = q.where(Comparison.object_key == object_key)
        row = db.execute(q.order_by(Comparison.created_at.desc()).limit(1)).scalar_one_or_none()
        return dict(row.result or {}, kind=row.kind) if row else None


@router.get("/quick")
def quick() -> dict:
    return {"items": AS.quick_buttons()}


@router.post("/message")
async def message(req: MessageRequest, request: Request) -> dict:
    if not (req.message and req.message.strip()) and not req.quick:
        raise HTTPException(400, {"code": "EMPTY_MESSAGE"})
    sid = request.state.session_id
    if not _limiter.allow(sid):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    with session_scope() as db:
        uid = _user_id(db, request)
    obj = req.context.object.model_dump() if req.context.object else None
    engine = AS.engine_from_settings()

    async def run(progress):
        comp = load_comparison(req.context.comparison_id, (obj or {}).get("key"), sid, uid)
        info = None
        main_id = (obj or {}).get("main_id")
        if main_id:
            info = cache.get_json("_external/objinfo", main_id, DAY)
        ctx = AS.Context(object=obj, comparison=comp, object_info=info)
        wants_object = req.quick == "object" or (
            not req.quick and any(e["id"] == "object" for _, e in AS.score(req.message or "")[:1])
        )
        if wants_object and info is None and main_id:
            try:
                ctx.object_info = await build_info(main_id, progress)
            except Exception:  # noqa: BLE001 - answered without the info panel then
                ctx.object_info = None

        topic = f"job:{jobs_id[0]}"
        for _ in range(int(SUBSCRIBE_WAIT_S / 0.05)):
            if manager.has_subscribers(topic):
                break
            await asyncio.sleep(0.05)
        final: AS.Answer | None = None
        async for piece in engine.reply(req.message, req.quick, ctx):
            if isinstance(piece, AS.Answer):
                final = piece
            else:
                await progress("assistant_chunk", {"text": piece})
                await asyncio.sleep(CHUNK_DELAY_S)
        assert final is not None
        log_action(request, "assistant", object_key=(obj or {}).get("key"), payload={"answer": final.source})
        return AS.to_json(final)

    jobs_id = [""]
    jobs_id[0] = jobs.start("assistant", run)
    return {"job_id": jobs_id[0]}
