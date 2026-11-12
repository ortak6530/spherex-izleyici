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
