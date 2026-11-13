"""Sources page / docs/SOURCES.md: every external resource is credited, and the two stay in sync."""

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS = tomllib.loads((ROOT / "config" / "attributions.toml").read_text("utf-8"))["item"]
BY_KEY = {i["key"]: i for i in ITEMS}

# Resources the project plan (DECISIONS.md §4e-a) requires on the page
REQUIRED = {"spherex", "irsa", "cds", "jpl", "wikipedia", "hst", "jwst", "gaia"}
REQUIRED |= {"cadc_ssois", "neossat", "wiseview"}


def test_every_required_source_is_listed():
    assert set(BY_KEY) >= REQUIRED
    assert len(BY_KEY) == len(ITEMS)  # unique keys


def test_items_have_required_fields():
    for it in ITEMS:
        assert it["title"] and it["purpose"] and it["url"].startswith("https://"), it["key"]
        assert it.get("group", "data") in ("data", "software"), it["key"]
        assert it.get("status") in ("used", "planned"), it["key"]
        if it.get("text") and it.get("text_source"):
            assert it.get("verified"), f"{it['key']}: verbatim text without a verification date"
        for c in it.get("citations", []) + it.get("references", []):
            assert c["label"] and c["url"].startswith("https://"), it["key"]


def test_mandatory_texts_and_citations():
    sp = BY_KEY["spherex"]
    assert sp["text"].startswith("This publication makes use of data products from the Spectro-Photometer")
    labels = " ".join(c["label"] for c in sp["citations"])
    for author in ("Bock", "Akeson", "Crill", "Korngut"):
        assert author in labels
    refs = " ".join(r["label"] for r in sp["references"])
    for tut in ("Data Overview", "Cutouts", "PSF", "Source Discovery", "Mosaic", "HiPS"):
        assert tut in refs
    assert "Gwyn" in BY_KEY["cadc_ssois"]["citations"][0]["label"]
    neo = BY_KEY["neossat"]
    assert "Open Government Licence" in neo["license"]
    assert "CSA-NEOSSAT-MAN-0002 v4.00" in " ".join(r["label"] for r in neo["references"])
    assert "Bishop's University" in neo["text"]
    assert "1806.004" in BY_KEY["wiseview"]["url"]


def test_sources_md_is_up_to_date():
    script = ROOT / "tools" / "gen_sources_md.py"
    r = subprocess.run([sys.executable, "-I", str(script), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_attributions_endpoint_serves_all(client):
    items = client.get("/api/v1/meta/attributions").json()["items"]
    assert {i["key"] for i in items} == set(BY_KEY)
