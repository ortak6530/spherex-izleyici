from fastapi import APIRouter

from ...config_loader import attributions, releases

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/releases")
def list_releases() -> dict:
    cfg = releases()
    return {
        "default": cfg.default_release,
        "releases": [
            {
                "id": r.id,
                "label": r.label,
                "status": r.status,
                "calib_family": r.calib_family,
                "doi": r.doi or None,
                "show_with_warning": r.show_with_warning,
                "announced": r.announced,
                "notice": r.notice or None if not r.announced else None,
                "notes": r.notes,
            }
            for r in cfg.release
        ],
        # Filled by the update pipeline (Phase 2/3); None means "not scanned yet", never a guess
        "last_update": None,
    }


@router.get("/attributions")
def list_attributions() -> dict:
    return {"items": attributions().get("item", [])}


@router.get("/links")
def list_links() -> dict:
    """External links panel: only links verified live, each also credited on the Sources page."""
    return {"items": attributions().get("link", [])}


# Upstreams shown in the status bar (group name in upstreams.toml -> label)
STATUS_UPSTREAMS = {"irsa": "IRSA", "cds": "SIMBAD", "jpl": "JPL"}


@router.get("/status")
def status() -> dict:
    """Data status bar: active releases, the archive's newest observation (background TAP check,
    services/freshness.py) and each upstream's state from the server's own last request.
    Nothing is guessed: unknown values are null ("not checked yet")."""
    from ...http import http
    from ...services import freshness

    cfg = releases()
    health = http.health()
    f = freshness.latest()
    return {
        "default": cfg.default_release,
        "releases": [
            {
                "id": r.id,
                "label": r.label,
                "doi": r.doi or None,
                "notice": r.notice or None if not r.announced else None,
            }
            for r in cfg.active
        ],
        "archive": None
        if not f
        else {
            "newest_utc": f["newest"]["date_utc"],
            "newest_release": f["newest"]["release"],
            "per_release": {k: v["date_utc"] for k, v in f["per_release"].items()},
            "checked_at": f["checked_at"],
            "source": f["source"],
        },
        "upstreams": [
            {
                "id": g,
                "label": label,
                **(
                    {"state": "ok" if h["ok"] else "error", **h}
                    if (h := health.get(g))
                    else {"state": "unknown"}
                ),
            }
            for g, label in STATUS_UPSTREAMS.items()
        ],
    }
