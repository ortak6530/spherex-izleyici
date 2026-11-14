"""Assistant: POST /assistant/message starts a job whose answer streams over WebSocket as
"assistant_chunk" progress steps (topic job:<id>); the job result holds the complete answer, so HTTP
polling alone also works. GET /assistant/quick lists the quick-question buttons (from the FAQ file).

What the assistant may read is loaded here, on the server: the comparison by id (only this browser's
or the signed-in user's) or else this browser's latest one, the cached object info, the number of
SPHEREx images from the cache (never a new archive query) and the archive's newest observation
(services/freshness.py). The question text is never stored: the admin log only gets an
"assistant_question" event without payload.
"""

from __future__ import annotations

import asyncio
import datetime as dt

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from ... import cache, jobs
from ...db import session_scope
from ...db.models import Comparison
from ...events import _user_id, log_action
from ...providers import most
from ...providers import spherex as S
from ...realtime import manager
from ...security import TokenBucket
from ...services import assistant as AS
from ...services import freshness
from .objects import DAY, build_info
from .resolve import resolve_target

router = APIRouter(prefix="/assistant", tags=["assistant"])
_limiter = TokenBucket(rate_per_min=20, burst=10)
CHUNK_DELAY_S = 0.035  # pacing of the typing effect
SUBSCRIBE_WAIT_S = 1.0  # give the browser time to subscribe to the job topic before streaming
EVENT_TYPE = "assistant_question"


class PageObject(BaseModel):
    """Labels of the open object (used for names only; numbers come from the server)."""

    key: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=120)
    query: str | None = Field(default=None, max_length=100)  # re-resolved on the server for counts
    kind: str | None = Field(default=None, pattern="^(object|coordinate|solar_system)$")
    main_id: str | None = Field(default=None, max_length=100)
    otype: str | None = Field(default=None, max_length=40)
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


async def image_count(obj: dict | None) -> int | None:
    """SPHEREx images for the open object, from cached results only (None = not computed yet)."""
    if not obj:
        return None
    if obj.get("kind") == "solar_system":
        des = obj.get("designation")
        today = dt.datetime.now(dt.UTC).date().isoformat()
        if (
            not des
            or cache.get_bytes("_external/most", f"{des}_{most.MISSION_START}_{today}", ".xml") is None
        ):
            return None
        try:  # served from the cache checked above
            return len((await most.moving_frames(des, most.MISSION_START, today))["frames"])
        except Exception:  # noqa: BLE001
            return None
    if not obj.get("query"):
        return None
    try:
        t = await resolve_target(obj["query"])  # cached name resolution (Sesame / SBDB)
    except Exception:  # noqa: BLE001
        return None
    if not t or t.get("ra") is None:
        return None
    return S.cached_coverage_count(t["ra"], t["dec"])


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
    topic: dict[str, str] = {}

    async def run(progress):
        comp = load_comparison(req.context.comparison_id, (obj or {}).get("key"), sid, uid)
        main_id = (obj or {}).get("main_id")
        info = cache.get_json("_external/objinfo", main_id, DAY) if main_id else None
        ctx = AS.Context(
            object=obj,
            comparison=comp,
            object_info=info,
            n_images=await image_count(obj),
            freshness=freshness.latest(),
        )
        wants_object = req.quick == "object" or (
            not req.quick and any(e["id"] == "object" for _, e in AS.score(req.message or "")[:1])
        )
        if wants_object and info is None and main_id:
            try:
                ctx.object_info = await build_info(main_id, progress)
            except Exception:  # noqa: BLE001 - answered without the info panel then
                ctx.object_info = None

        for _ in range(int(SUBSCRIBE_WAIT_S / 0.05)):
            if manager.has_subscribers(topic["name"]):
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
        return AS.to_json(final)

    job_id = jobs.start("assistant", run)
    topic["name"] = f"job:{job_id}"  # set before the job's first await
    # Admin log: only that a question was asked; no text, no object, no answer type
    log_action(request, EVENT_TYPE)
    return {"job_id": job_id}
