"""Generate docs/SOURCES.md from config/attributions.toml (the single source of truth).

Usage (from the repo root):
    backend\\.venv\\Scripts\\python.exe tools\\gen_sources_md.py          # print the Markdown
    backend\\.venv\\Scripts\\python.exe tools\\gen_sources_md.py --check  # exit 1 if docs/SOURCES.md differs

The script never writes files (project rule: files change only through the editor tools);
paste the printed Markdown into docs/SOURCES.md. backend/tests/test_sources.py runs --check.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "attributions.toml"
OUT = ROOT / "docs" / "SOURCES.md"

STATUS = {"used": "Kullanılıyor", "planned": "Planlandı"}
GROUPS = [("data", "Veri kaynakları ve servisler"), ("software", "Yazılım")]


def render(items: list[dict]) -> str:
    lines = [
        "# Kaynaklar ve atıflar",
        "",
        "> Bu dosya `config/attributions.toml` dosyasından **üretilir**; elle düzenlemeyin.",
        "> Güncel çıktı: `backend\\.venv\\Scripts\\python.exe tools\\gen_sources_md.py` (test: `--check`).",
        "> Aynı içerik sitede **Kaynaklar** sayfasında (`/#kaynaklar`, alt bilgideki bağlantı) gösterilir.",
        "",
        "Yarışma kuralı gereği sitenin kullandığı **her** dış kaynak burada anılır. Teşekkür metinleri",
        "sağlayıcının sayfasından **aynen** alınmıştır; nereden ve ne zaman alındığı her metnin altında yazar.",
        "\"Planlandı\" işaretli kaynaklar henüz kullanılmıyor.",
        "",
        "| Kaynak | Durum | Kullanım amacı |",
        "|---|---|---|",
    ]
    for it in items:
        lines.append(f"| {it['title']} | {STATUS.get(it.get('status', 'used'), '?')} | {it.get('purpose', '')} |")
    for gkey, gtitle in GROUPS:
        group = [i for i in items if i.get("group", "data") == gkey]
        if not group:
            continue
        lines += ["", f"## {gtitle}"]
        for it in group:
            lines += ["", f"### {it['title']}", ""]
            lines.append(f"- **Durum:** {STATUS.get(it.get('status', 'used'), '?')}")
            if it.get("purpose"):
                lines.append(f"- **Kullanım amacı:** {it['purpose']}")
            if it.get("url"):
                lines.append(f"- **Adres:** <{it['url']}>")
            if it.get("license"):
                lines.append(f"- **Lisans / koşullar:** {it['license']}")
            if it.get("dois"):
                lines.append(f"- **DOI:** {' · '.join(it['dois'])}")
            if it.get("text"):
                src = it.get("text_source", "")
                when = f", {it['verified']} tarihinde doğrulandı" if it.get("verified") else ""
                lines += ["", f"> {it['text']}", ""]
                if src:
                    lines.append(f"Metnin alındığı yer: {src}{when}.")
            if it.get("note"):
                lines += ["", f"_Not:_ {it['note']}"]
            if it.get("citations"):
                lines += ["", "Atıf yapılacak yayınlar:", ""]
                lines += [f"- [{c['label']}]({c['url']})" for c in it["citations"]]
            if it.get("references"):
                lines += ["", "Başvurulan belgeler:", ""]
                lines += [f"- [{r['label']}]({r['url']})" for r in it["references"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    items = tomllib.loads(CONFIG.read_text("utf-8"))["item"]
    text = render(items)
    if "--check" in sys.argv:
        current = OUT.read_text("utf-8").replace("\r\n", "\n") if OUT.exists() else ""
        if current != text:
            print("docs/SOURCES.md is out of date; regenerate it from tools/gen_sources_md.py")
            return 1
        return 0
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
