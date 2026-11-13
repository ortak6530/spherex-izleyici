"""tools/prewarm.py makes the same choices as the UI (pair and visit selection)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("prewarm", ROOT / "tools" / "prewarm.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)


def img(i, lam, bw=0.04, on=True):
    return {"image_id": f"dr1:x_{i}:D5", "wavelength_um": lam, "bandwidth_um": bw, "on_detector": on}


def test_targets_are_the_requested_demo_objects():
    assert set(P.TARGETS) == {"3i_atlas", "barnard", "wise0855", "luhman16"}


def test_best_pair_picks_smallest_channel_difference():
    a = [img(1, 4.10), img(2, 4.20), img(3, 4.30, on=False)]
    b = [img(4, 4.29), img(5, 4.205), img(6, None)]
    pa, pb, ratio = P.best_pair(a, b)
    assert (pa["image_id"], pb["image_id"]) == ("dr1:x_2:D5", "dr1:x_5:D5")
    assert ratio == pytest.approx(0.005 / 0.04)


def test_best_pair_none_without_usable_images():
    assert P.best_pair([img(1, None)], [img(2, 4.2)]) is None


def test_brightest_visit_matches_the_ui_default():
    res = {
        "frames": [
            {"image_id": "a", "vmag": 14.0},
            {"image_id": "b", "vmag": 13.1},
            {"image_id": "c", "vmag": None},
        ],
        "visits": [
            {"frame_ids": ["a"], "start": "2025-08-01"},
            {"frame_ids": ["b", "c"], "start": "2025-12-08"},
        ],
    }
    assert P.brightest_visit(res)["start"] == "2025-12-08"
