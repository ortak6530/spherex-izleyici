from fastapi import APIRouter, HTTPException, Path

from ... import jobs

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
def get_job(job_id: str = Path(pattern=r"^[A-Za-z0-9_-]{6,64}$")) -> dict:
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(404, {"code": "UNKNOWN_JOB"})
    return j
