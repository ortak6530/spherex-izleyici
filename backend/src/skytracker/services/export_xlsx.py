"""Excel export (openpyxl): Özet, Gözlemler, Zaman karşılaştırması, Cisim karşılaştırması, Hareket.

Pure formatting: the API module gathers the data (cached archive results and stored comparisons) and
passes plain dicts here. Rules (DECISIONS §2.4):
- no raw pixels, only FITS links; at most MAX_ROWS rows per sheet (the cut is noted in Özet);
- formula injection: text starting with = + - @ (and tab / CR) gets a leading apostrophe;
- every number shown comes from the archive or the site's own computation, with its source.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import unicodedata
from typing import Any

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

MAX_ROWS = 5000
MAX_CELL_CHARS = 32000  # Excel's limit is 32 767
_DANGEROUS_START = ("=", "+", "-", "@", "\t", "\r")
_HEADER_FILL = PatternFill("solid", fgColor="1F2A44")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_TITLE_FONT = Font(bold=True, size=14)
_BOLD = Font(bold=True)
_LINK_FONT = Font(color="0563C1", underline="single")

# Same wording as the site (frontend/src/i18n/tr.json "warnings.*")
WARNING_TEXT = {
    "CHANNEL_WARN": "Dalga boyları yakın ama aynı değil (Δλ = {dl} nm, bant genişliğinin {ratio} katı).",
    "CROSS_RELEASE": "A ve B farklı veri sürümlerinden ({a} / {b}). {fix}",
    "PIPELINE_DIFFERS": "Aynı sürüm içinde farklı boru hattı sürümleri ({a} / {b}).",
    "NO_BACKGROUND": "Yerel arka plan çıkarılamadı (alanın tamamı kaynak olarak işaretli).",
    "NORMALIZATION_UNRELIABLE": "Göreli normalleştirme için yeterli alan pikseli yok; uygulanmadı.",
    "LOW_SNR": "Hedefin sinyal/gürültü oranı düşük ({snr}); farklar gürültü olabilir.",
    "HIGH_MASK_FRACTION": "Dönem {epoch} piksellerinin %{pct}'i maskeli.",
    "ATMOSPHERIC_LINE": "Dönem {epoch} dalga boyu çıkarılmamış bir atmosferik çizgiye yakın: {lines}.",
    "TARGET_NEAR_EDGE": "Dönem {epoch}: hedef kesitin kenarına çok yakın.",
    "PROPER_MOTION_APPLIED": "Hedef konumu her tarih için SIMBAD öz hareketiyle hesaplandı.",
    "SATURATED_OR_MASKED_CORE": "Dönem {epoch}: hedefin merkezi doymuş veya maskeli; fotometri yapılamadı.",
    "NO_PHOTOMETRY": "Dönem {epoch}: açıklıkta yeterli geçerli piksel yok; parlaklık ölçülmedi.",
    "DIFFERENT_TYPES": "İki cisim farklı türden ({a} / {b}); karşılaştırma yalnızca görünüm amaçlıdır.",
}
CHANNEL_TEXT = {"match": "Aynı kanal", "warn": "Yakın kanal (uyarı)", "reject": "Farklı kanal"}


def safe(v: Any) -> Any:
    """Cell value: numbers as numbers, text cleaned and defused against formula injection."""
    if v is None or isinstance(v, bool | int | float):
        return v
    s = ILLEGAL_CHARACTERS_RE.sub("", str(v))[:MAX_CELL_CHARS]
    return "'" + s if s.startswith(_DANGEROUS_START) else s


def _fmt(v: float | None, nd: int) -> str:
    return "?" if v is None else f"{v:.{nd}f}".replace(".", ",")


def warning_text(w: dict) -> str:
    code = w.get("code", "")
    p = dict(w)
    if code == "CHANNEL_WARN":
        p["dl"] = _fmt((w.get("delta_um") or 0) * 1000, 1)
        p["ratio"] = _fmt(w.get("ratio"), 2)
    elif code == "CROSS_RELEASE":
        p["fix"] = (
            "QR2 görüntüsüne IRSA'nın QR3 akı düzeltmesi uygulandı."
            if w.get("flux_corrected")
            else "Akı düzeltmesi uygulanamadı; mutlak parlaklıkları karşılaştırmayın."
        )
    elif code == "LOW_SNR":
        p["snr"] = _fmt(w.get("snr"), 1)
    elif code == "HIGH_MASK_FRACTION":
        p["pct"] = _fmt((w.get("fraction") or 0) * 100, 0)
    elif code == "ATMOSPHERIC_LINE":
        p["lines"] = ", ".join(w.get("lines") or [])
    if "epoch" in p:
        p["epoch"] = str(p["epoch"]).upper()
    tpl = WARNING_TEXT.get(code)
    if tpl is None:
        return code
    try:
        return tpl.format(**p)
    except (KeyError, IndexError, ValueError):
        return code


def warnings_text(ws: list[dict] | None) -> str | None:
    return " | ".join(warning_text(w) for w in ws) if ws else None


def sexagesimal(ra: float | None, dec: float | None) -> str | None:
    if ra is None or dec is None:
        return None
    h = ra / 15.0
    hh, mm = int(h), int((h * 60) % 60)
    ss = (h * 3600) % 60
    sign = "-" if dec < 0 else "+"
    d = abs(dec)
    dd, dm = int(d), int((d * 60) % 60)
    ds = (d * 3600) % 60
    return f"{hh:02d}h{mm:02d}m{ss:05.2f}s {sign}{dd:02d}°{dm:02d}′{ds:04.1f}″"


_TR = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iIsSgGuUoOcC")


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.translate(_TR)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:60] or "cisim"


def filename_for(names: list[str], today: dt.date) -> str:
    base = slug(names[0]) if len(names) == 1 else "cisim-listesi"
    return f"{base}_{today.isoformat()}.xlsx"


# ---------- sheet helpers ----------


class Sheet:
    """A table sheet: header row, typed columns, row cap, clickable links."""

    def __init__(self, wb: Workbook, title: str, columns: list[tuple[str, int, str | None]], note: str):
        self.ws: Worksheet = wb.create_sheet(title)
        self.columns = columns
        self.ws.append([safe(note)])
        self.ws["A1"].font = Font(italic=True, color="555555")
        self.ws.append([safe(c[0]) for c in columns])
        for i, (_, width, _) in enumerate(columns, start=1):
            cell = self.ws.cell(row=2, column=i)
            cell.fill, cell.font = _HEADER_FILL, _HEADER_FONT
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            self.ws.column_dimensions[get_column_letter(i)].width = width
        self.ws.freeze_panes = "A3"
        self.rows = 0
        self.truncated = 0

    def add(self, values: list[Any]) -> None:
        if self.rows >= MAX_ROWS:
            self.truncated += 1
            return
        self.ws.append([safe(v) for v in values])
        self.rows += 1
        r = self.ws.max_row
        for i, (_, _, fmt) in enumerate(self.columns, start=1):
            cell = self.ws.cell(row=r, column=i)
            if fmt == "link":
                if isinstance(cell.value, str) and cell.value.startswith("https://"):
                    cell.hyperlink = cell.value
                    cell.font = _LINK_FONT
            elif fmt and isinstance(cell.value, int | float) and not isinstance(cell.value, bool):
                cell.number_format = fmt

    def finish(self) -> None:
        if self.rows:
            self.ws.auto_filter.ref = f"A2:{get_column_letter(len(self.columns))}{self.ws.max_row}"


def yes_no(v: bool | None) -> str | None:
    return None if v is None else ("evet" if v else "hayır")


def _get(d: dict | None, *path: str) -> Any:
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


# ---------- workbook ----------

OBS_COLS = [
    ("Cisim", 22, None),
    ("Tarih (UTC)", 20, None),
    ("MJD", 12, "0.00000"),
    ("Ziyaret", 26, None),
    ("Veri sürümü", 11, None),
    ("Dedektör", 9, None),
    ("λ hedefte (µm)", 13, "0.0000"),
    ("Bant genişliği (µm)", 13, "0.0000"),
    ("Kanal (yaklaşık, 1–17)", 11, "0"),
    ("Dedektör aralığı (µm)", 16, None),
    ("Hedef dedektörde", 10, None),
    ("Gözlem kimliği", 26, None),
    ("Boru hattı sürümü", 14, None),
    ("FITS bağlantısı", 60, "link"),
]

TIME_COLS = [
    ("Cisim", 22, None),
    ("Karşılaştırma kimliği", 18, None),
    ("Hesaplandı (UTC)", 20, None),
    ("Dönem A (UTC)", 20, None),
    ("Dönem B (UTC)", 20, None),
    ("Δt (gün)", 10, "0.0"),
    ("Sürüm A", 9, None),
    ("Sürüm B", 9, None),
    ("Dedektör", 9, None),
    ("λ A (µm)", 10, "0.0000"),
    ("λ B (µm)", 10, "0.0000"),
    ("Δλ (nm)", 9, "0.0"),
    ("Kanal eşleşmesi", 16, None),
    ("Δλ / bant genişliği", 11, "0.00"),
    ("Kayma (piksel)", 11, "0.00"),
    ("Kayma (″)", 10, "0.00"),
    ("Kayma yönü (°, K→D)", 11, "0"),
    ("Beklenen kayma (″, SIMBAD öz hareketi)", 16, "0.00"),
    ("Beklenen kayma (piksel)", 12, "0.00"),
    ("Akı A (µJy)", 12, "0.0"),
    ("Akı A hatası (µJy)", 12, "0.0"),
    ("Akı B (µJy)", 12, "0.0"),
    ("Akı B hatası (µJy)", 12, "0.0"),
    ("Parlaklık farkı (%)", 11, "0.0"),
    ("Parlaklık farkı hatası (%)", 11, "0.0"),
    ("Anlamlılık (σ)", 10, "0.0"),
    ("Normalleştirilmiş fark (%)", 12, "0.0"),
    ("Normalleştirme çarpanı", 12, "0.000"),
    ("Kesit boyutu (°)", 9, "0.00"),
    ("Zodyak ışığı", 12, None),
    ("Uyarılar", 60, None),
    ("FITS A", 50, "link"),
    ("FITS B", 50, "link"),
]

OBJ_COLS = [
    ("Karşılaştırma kimliği", 18, None),
    ("Hesaplandı (UTC)", 20, None),
    ("Cisim A", 22, None),
    ("Cisim B", 22, None),
    ("Tür A", 14, None),
    ("Tür B", 14, None),
    ("Aynı tür", 9, None),
    ("Tayf türü A", 12, None),
    ("Tayf türü B", 12, None),
    ("Uzaklık A (pc)", 12, "0.00"),
    ("Uzaklık B (pc)", 12, "0.00"),
    ("Tarih A (UTC)", 20, None),
    ("Tarih B (UTC)", 20, None),
    ("Sürüm A", 9, None),
    ("Sürüm B", 9, None),
    ("Dedektör", 9, None),
    ("λ A (µm)", 10, "0.0000"),
    ("λ B (µm)", 10, "0.0000"),
    ("Kanal eşleşmesi", 16, None),
    ("Akı A (µJy)", 12, "0.0"),
    ("Akı A hatası (µJy)", 12, "0.0"),
    ("Akı B (µJy)", 12, "0.0"),
    ("Akı B hatası (µJy)", 12, "0.0"),
    ("AB kadiri A", 10, "0.00"),
    ("AB kadiri B", 10, "0.00"),
    ("Akı oranı B/A", 11, "0.000"),
    ("Uyarılar", 60, None),
    ("FITS A", 50, "link"),
    ("FITS B", 50, "link"),
]

MOVE_COLS = [
    ("Cisim", 22, None),
    ("Tanım (JPL)", 12, None),
    ("Tarih (UTC)", 20, None),
    ("MJD", 12, "0.00000"),
    ("Veri sürümü", 11, None),
    ("Dedektör", 9, None),
    ("RA (°, J2000)", 12, "0.00000"),
    ("Dec (°, J2000)", 12, "0.00000"),
    ("Güneş uzaklığı r (AU)", 11, "0.000"),
    ("Yer/gözlemci uzaklığı Δ (AU)", 12, "0.000"),
    ("Faz açısı (°)", 9, "0.0"),
    ("Öngörülen V kadiri", 10, "0.0"),
    ("Kare merkezine uzaklık (°)", 11, "0.000"),
    ("Gözlem kimliği", 26, None),
    ("FITS bağlantısı", 60, "link"),
]


def _summary_sheet(wb: Workbook, objects: list[dict], meta: dict, sources: list[dict], cut: dict) -> None:
    ws = wb.active
    ws.title = "Özet"
    ws["A1"] = "SPHEREx Gökyüzü İzleyici — veri dışa aktarımı"
    ws["A1"].font = _TITLE_FONT
    info_rows = [
        ("Oluşturulma (UTC)", meta["generated_at"]),
        ("Site", meta["site_url"]),
        ("Cisim sayısı", len(objects)),
        ("Uygulanan filtreler", meta.get("filters_text") or "yok"),
        (
            "Not",
            "Ham piksel verisi bu dosyada yoktur; her görüntü için IRSA FITS bağlantısı verilmiştir. "
            "Her sayfa en fazla 5.000 satırdır.",
        ),
        (
            "λ (dalga boyu)",
            "Hedefin bulunduğu pikseldeki dalga boyu (SPHEREx doğrusal değişken süzgeci, FITS WCS-WAVE). "
            "Sitede görüntülenen dedektör için hesaplanır; diğer dedektörlerde yalnızca daha önce "
            "hesaplanmışsa doludur, değilse 'Dedektör aralığı' sütununa bakın.",
        ),
    ]
    for k, v in cut.items():
        if v:
            info_rows.append(("Kesilen satırlar", f"{k}: 5.000 satır sınırı nedeniyle {v} satır eklenmedi."))
    r = 3
    for k, v in info_rows:
        ws.cell(row=r, column=1, value=safe(k)).font = _BOLD
        ws.cell(row=r, column=2, value=safe(v)).alignment = Alignment(wrap_text=True, vertical="top")
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Cisimler").font = _TITLE_FONT
    r += 1
    head = [
        "Ad",
        "Ana kimlik (SIMBAD)",
        "Tür",
        "Tür açıklaması",
        "Tayf türü",
        "RA (°)",
        "Dec (°)",
        "RA / Dec",
        "Konum notu",
        "Uzaklık (pc)",
        "Uzaklık (ışık yılı)",
        "Uzaklık yöntemi",
        "Açıklama (Vikipedi)",
        "Vikipedi bağlantısı",
        "Bilgi kaynağı",
        "Gözlem satırı",
        "Zaman karşılaştırması",
        "Cisim karşılaştırması",
        "Hareket karesi",
        "Not",
    ]
    for i, h in enumerate(head, start=1):
        c = ws.cell(row=r, column=i, value=h)
        c.fill, c.font = _HEADER_FILL, _HEADER_FONT
        c.alignment = Alignment(wrap_text=True, vertical="top")
    for o in objects:
        r += 1
        t, info = o.get("target") or {}, o.get("info") or {}
        sim, wk, dist = info.get("simbad") or {}, info.get("wikipedia") or {}, info.get("distance") or {}
        pos_note = None
        if t.get("kind") == "object" and t.get("epoch"):
            pos_note = f"SPHEREx arama dönemi {t['epoch']} (SIMBAD öz hareketiyle)"
        elif t.get("kind") == "solar_system":
            pos_note = "Güneş Sistemi cismi: konumlar 'Hareket' sayfasında"
        values = [
            o.get("name"),
            t.get("main_id"),
            sim.get("otype") or t.get("otype"),
            sim.get("otype_desc") or t.get("orbit_class"),
            sim.get("sp_type"),
            t.get("ra"),
            t.get("dec"),
            sexagesimal(t.get("ra"), t.get("dec")),
            pos_note,
            dist.get("pc"),
            dist.get("ly"),
            f"{dist['method']} ({dist['source']})" if dist else None,
            wk.get("extract"),
            wk.get("url"),
            " · ".join(filter(None, [*(info.get("sources") or {}).values(), t.get("source")])) or None,
            o.get("n_observations", 0),
            len(o.get("time_comparisons") or []),
            len(o.get("object_comparisons") or []),
            len((o.get("moving") or {}).get("frames") or []),
            " ".join(o.get("notes") or []) or None,
        ]
        for i, v in enumerate(values, start=1):
            c = ws.cell(row=r, column=i, value=safe(v))
            c.alignment = Alignment(wrap_text=i in (13, 20), vertical="top")
            if i in (6, 7) and isinstance(v, float):
                c.number_format = "0.000000"
            if i == 14 and isinstance(c.value, str) and c.value.startswith("https://"):
                c.hyperlink, c.font = c.value, _LINK_FONT

    r += 2
    ws.cell(row=r, column=1, value="Veri kaynakları ve atıf").font = _TITLE_FONT
    r += 1
    ws.cell(row=r, column=1, value=safe("Teşekkür metinleri sağlayıcıların sayfalarından aynen alınmıştır."))
    r += 1
    for i, h in enumerate(
        ["Kaynak", "Kullanım", "Teşekkür metni", "Kaynak sayfası", "Lisans / not"], start=1
    ):
        c = ws.cell(row=r, column=i, value=h)
        c.fill, c.font = _HEADER_FILL, _HEADER_FONT
    for s in sources:
        r += 1
        vals = [
            s.get("title"),
            s.get("purpose"),
            s.get("text"),
            s.get("text_source") or s.get("url"),
            s.get("license") or s.get("note"),
        ]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=i, value=safe(v))
            c.alignment = Alignment(wrap_text=i in (2, 3, 5), vertical="top")
            if i == 4 and isinstance(c.value, str) and c.value.startswith("https://"):
                c.hyperlink, c.font = c.value, _LINK_FONT
        for cit in s.get("citations") or []:
            r += 1
            ws.cell(row=r, column=2, value=safe("Atıf: " + str(cit.get("label"))))
            c = ws.cell(row=r, column=4, value=safe(cit.get("url")))
            if isinstance(c.value, str) and c.value.startswith("https://"):
                c.hyperlink, c.font = c.value, _LINK_FONT

    for col, width in zip(
        "ABCDEFGHIJKLMNOPQRST",
        (24, 26, 12, 22, 12, 12, 12, 26, 30, 11, 12, 18, 60, 40, 30, 10, 12, 12, 10, 40),
        strict=True,
    ):
        ws.column_dimensions[col].width = width


def _time_row(name: str, c: dict) -> list:
    a, b, ch = c.get("a") or {}, c.get("b") or {}, c.get("channel") or {}
    sh, ex, ph = c.get("shift") or {}, c.get("expected_shift") or {}, c.get("photometry") or {}
    chg, chn = ph.get("change") or {}, ph.get("change_normalized") or {}
    return [
        name,
        c.get("id"),
        c.get("_created_at"),
        a.get("date_obs"),
        b.get("date_obs"),
        c.get("dt_days"),
        a.get("release"),
        b.get("release"),
        a.get("detector"),
        a.get("wavelength_um"),
        b.get("wavelength_um"),
        None if ch.get("delta_um") is None else ch["delta_um"] * 1000,
        CHANNEL_TEXT.get(ch.get("status"), ch.get("status")),
        ch.get("ratio"),
        sh.get("px"),
        sh.get("arcsec"),
        sh.get("pa_deg"),
        ex.get("arcsec"),
        ex.get("px"),
        _get(ph, "a", "flux_ujy"),
        _get(ph, "a", "err_ujy"),
        _get(ph, "b", "flux_ujy"),
        _get(ph, "b", "err_ujy"),
        chg.get("percent"),
        chg.get("err_percent"),
        chg.get("significance"),
        chn.get("percent"),
        _get(c, "normalization", "factor"),
        c.get("size_deg"),
        "çıkarıldı" if c.get("zodi") == "sub" else "ham" if c.get("zodi") else None,
        warnings_text(c.get("warnings")),
        a.get("fits_url"),
        b.get("fits_url"),
    ]


def _object_row(c: dict) -> list:
    oa, ob = _get(c, "objects", "a") or {}, _get(c, "objects", "b") or {}
    va, vb, ch = c.get("a_view") or {}, c.get("b_view") or {}, c.get("channel") or {}
    return [
        c.get("id"),
        c.get("_created_at"),
        oa.get("name"),
        ob.get("name"),
        oa.get("otype_desc") or oa.get("otype"),
        ob.get("otype_desc") or ob.get("otype"),
        yes_no(c.get("same_type")),
        oa.get("sp_type"),
        ob.get("sp_type"),
        _get(oa, "distance", "pc"),
        _get(ob, "distance", "pc"),
        va.get("date_obs"),
        vb.get("date_obs"),
        va.get("release"),
        vb.get("release"),
        va.get("detector"),
        va.get("wavelength_um"),
        vb.get("wavelength_um"),
        CHANNEL_TEXT.get(ch.get("status"), ch.get("status")),
        _get(va, "photometry", "flux_ujy"),
        _get(va, "photometry", "err_ujy"),
        _get(vb, "photometry", "flux_ujy"),
        _get(vb, "photometry", "err_ujy"),
        va.get("ab_mag"),
        vb.get("ab_mag"),
        c.get("flux_ratio_b_over_a"),
        warnings_text(c.get("warnings")),
        va.get("fits_url"),
        vb.get("fits_url"),
    ]


def build_workbook(objects: list[dict], meta: dict, sources: list[dict]) -> tuple[bytes, dict]:
    """objects: one dict per object (target, info, observations, comparisons, moving, notes).

    Returns the .xlsx bytes and row counts per sheet.
    """
    wb = Workbook()
    obs = Sheet(
        wb,
        "Gözlemler",
        OBS_COLS,
        "SPHEREx spektral görüntüleri (IRSA SIA2). λ: hedefin pikselindeki dalga boyu. "
        "Ham piksel yok; FITS bağlantısından indirilebilir.",
    )
    for o in objects:
        for row in o.get("observations") or []:
            obs.add([o.get("name"), *row])
    obs.finish()

    sheets: dict[str, Sheet] = {"Gözlemler": obs}
    time_rows = [(o.get("name"), c) for o in objects for c in o.get("time_comparisons") or []]
    if time_rows:
        s = Sheet(
            wb,
            "Zaman karşılaştırması",
            TIME_COLS,
            "Aynı cismin iki dönemi; değerler sitenin hesapladığı sonuçlardır (kayma: ağırlık merkezi, "
            "parlaklık: açıklık fotometrisi, hata +%3 sistematik dahil).",
        )
        for name, c in time_rows:
            s.add(_time_row(name, c))
        s.finish()
        sheets["Zaman karşılaştırması"] = s

    obj_rows = [c for o in objects for c in o.get("object_comparisons") or []]
    if obj_rows:
        s = Sheet(
            wb,
            "Cisim karşılaştırması",
            OBJ_COLS,
            "İki cisim aynı dalga boyu kanalında; tür, tayf türü ve uzaklık SIMBAD'dan, akılar SPHEREx'ten.",
        )
        for c in obj_rows:
            s.add(_object_row(c))
        s.finish()
        sheets["Cisim karşılaştırması"] = s

    moving = [(o.get("name"), o["moving"]) for o in objects if (o.get("moving") or {}).get("frames")]
    if moving:
        s = Sheet(
            wb,
            "Hareket",
            MOVE_COLS,
            "Konumlar, IRSA MOST'un JPL Horizons ile hesapladığı öngörülen konumlardır; ölçüm değildir.",
        )
        for name, m in moving:
            for f in m["frames"]:
                s.add(
                    [
                        name,
                        m.get("designation"),
                        f.get("date_obs"),
                        f.get("mjd"),
                        f.get("release"),
                        f.get("detector"),
                        f.get("ra"),
                        f.get("dec"),
                        f.get("sun_dist_au"),
                        f.get("geo_dist_au"),
                        f.get("phase_deg"),
                        f.get("vmag"),
                        f.get("dist_ctr_deg"),
                        f.get("obs_id"),
                        f.get("fits_url"),
                    ]
                )
        s.finish()
        sheets["Hareket"] = s

    _summary_sheet(wb, objects, meta, sources, {k: v.truncated for k, v in sheets.items()})
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), {k: v.rows for k, v in sheets.items()}
