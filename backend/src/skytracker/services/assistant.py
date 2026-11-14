"""Rule-based assistant (no external AI): FAQ matching + interpretation of real comparison values.

`AssistantEngine` is the seam: `reply()` yields text pieces and finally one `Answer`. The rule-based
engine computes the whole answer first and then yields it in small pieces (the "typing" effect is
paced by the API layer). A language-model engine could later implement the same protocol.

Rules (DECISIONS §2.8, §5): answers come from config/assistant_faq.json or from values the server
computed and stored (`comparison` table, cached object info). Numbers sent by the browser are never
used; a missing value is never invented ("önce bir karşılaştırma yap").
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from ..providers import names
from ..settings import get_settings
from .export_xlsx import CHANNEL_TEXT, warning_text

MAX_MESSAGE = 500
SHIFT_AGREE_PX = 0.5  # measured vs. expected shift within half a pixel -> "uyumlu"
SIGNIFICANT_SIGMA = 3.0


@dataclass
class Context:
    """What the assistant may read. The comparison and object info are loaded on the server."""

    object: dict | None = None  # target labels from the page (name, kind, key, main_id, designation)
    comparison: dict | None = None  # stored result (no pixel arrays), see api/v1/compare.py
    object_info: dict | None = None  # cached /objects/info result


@dataclass
class Answer:
    text: str
    source: str  # "faq:<id>" | "interpret" | "object" | "open_object" | "greeting" | "fallback"
    suggestions: list[dict] = field(default_factory=list)  # [{id, label}]
    action: dict | None = None  # {"type": "open_object", "q": "..."} -> the page runs that search


class AssistantEngine(Protocol):
    def reply(self, message: str | None, quick: str | None, ctx: Context) -> AsyncIterator[str | Answer]: ...


# ---------- FAQ ----------


@lru_cache
def faq() -> dict:
    data = json.loads((get_settings().config_dir / "assistant_faq.json").read_text("utf-8"))
    for e in data["entries"]:
        e["_kw"] = [(names.normalize(k).split(), float(w)) for k, w in e.get("keywords", {}).items()]
    data["_by_id"] = {e["id"]: e for e in data["entries"]}
    return data


def quick_buttons() -> list[dict]:
    return [{"id": e["id"], "label": e["quick"]} for e in faq()["entries"] if e.get("quick")]


def _label(entry_id: str) -> dict | None:
    e = faq()["_by_id"].get(entry_id)
    if not e:
        return None
    return {"id": e["id"], "label": e.get("quick") or e.get("question") or e["id"]}


def _suggest(ids: list[str]) -> list[dict]:
    return [s for s in (_label(i) for i in ids) if s]


def _word_match(kw: str, word: str) -> bool:
    # Turkish is agglutinative: 4+ letter keywords also match suffixed forms ("piksel" ~ "pikselli")
    return word == kw or (len(kw) >= 4 and word.startswith(kw))


def _phrase_in(words: list[str], phrase: list[str]) -> bool:
    n = len(phrase)
    return any(all(_word_match(phrase[j], words[i + j]) for j in range(n)) for i in range(len(words) - n + 1))


def score(message: str) -> list[tuple[float, dict]]:
    words = names.normalize(message).split()
    out = []
    for e in faq()["entries"]:
        s = sum(w for phrase, w in e["_kw"] if phrase and _phrase_in(words, phrase))
        if s > 0:
            out.append((s, e))
    out.sort(key=lambda x: -x[0])
    return out


_GREETING = re.compile(r"^(merhaba|selam|selamlar|hey|hello|hi|gunaydin|iyi aksamlar|iyi gunler)\b")


# ---------- number formatting (Turkish decimal comma) ----------


def num(v: float | None, nd: int = 2) -> str:
    if v is None:
        return "?"
    s = f"{v:,.{nd}f}".replace(",", " ").replace(".", ",")
    return s


def day(iso: str | None) -> str:
    return (iso or "?")[:10]


# ---------- interpretation ----------


def interpret_time(c: dict) -> str:
    a, b, ch = c.get("a") or {}, c.get("b") or {}, c.get("channel") or {}
    parts = []
    dt = c.get("dt_days")
    rel_a, rel_b = (str(x.get("release") or "?").upper() for x in (a, b))
    det = a.get("detector")
    parts.append(
        f"Bu zaman karşılaştırması {day(a.get('date_obs'))} (Dönem A, {rel_a}) ile "
        f"{day(b.get('date_obs'))} (Dönem B, {rel_b}) arasındaki "
        f"{num(dt, 0) if dt is not None else '?'} günü kapsıyor"
        + (f"; D{det}, λ ≈ {num(a.get('wavelength_um'), 3)} µm." if det else ".")
    )
    if ch.get("status"):
        dl = ch.get("delta_um")
        parts.append(
            f"Kanal: {CHANNEL_TEXT.get(ch['status'], ch['status']).lower()} "
            f"(Δλ = {num(abs(dl) * 1000 if dl is not None else None, 1)} nm, "
            f"bant genişliğinin {num(ch.get('ratio'), 2)} katı)."
        )
    sh, ex = c.get("shift"), c.get("expected_shift")
    if sh:
        s = (
            f"Hedefin ağırlık merkezi {num(sh.get('arcsec'))}″ ({num(sh.get('px'))} piksel) kaymış; "
            f"yön {num(sh.get('pa_deg'), 0)}° (kuzeyden doğuya)."
        )
        if ex and ex.get("px") is not None and sh.get("px") is not None:
            diff = abs(sh["px"] - ex["px"])
            s += f" SIMBAD öz hareketinden beklenen kayma {num(ex.get('arcsec'))}″ ({num(ex['px'])} piksel)"
            if diff <= SHIFT_AGREE_PX:
                s += f"; fark {num(diff)} piksel, yani ölçüm bilinen hareketle uyumlu ✓"
            else:
                s += (
                    f"; fark {num(diff)} piksel, yarım pikselden büyük. Doymuş ya da maskeli bir merkez "
                    "ağırlık merkezini kaydırabilir; sonucu dikkatle yorumla."
                )
            s += "."
        elif sh.get("px") is not None and sh["px"] < 1:
            s += " Kayma bir pikselden küçük; tek başına hareket kanıtı sayılmaz."
        parts.append(s)
    else:
        parts.append("Hedefin konumu iki dönemde birden ölçülemedi, bu yüzden kayma verilmiyor.")

    ph = c.get("photometry") or {}
    chg = ph.get("change")
    if chg and chg.get("percent") is not None:
        sig = chg.get("significance")
        s = f"Parlaklık farkı (B − A): %{num(chg['percent'], 1)} ± {num(chg.get('err_percent'), 1)}"
        if sig is not None:
            s += (
                f" ({num(sig, 1)}σ, anlamlı)"
                if sig >= SIGNIFICANT_SIGMA
                else f" ({num(sig, 1)}σ; {num(SIGNIFICANT_SIGMA, 0)}σ'nın altında, anlamlı değişim yok)"
            )
        s += "."
        cn = ph.get("change_normalized")
        if cn and cn.get("percent") is not None:
            s += (
                f" Göreli normalleştirmeden sonra: %{num(cn['percent'], 1)}"
                f" ± {num(cn.get('err_percent'), 1)}."
            )
        parts.append(s)
    else:
        parts.append("Parlaklık farkı ölçülemedi (ör. merkez doymuş ya da maskeli); site değer uydurmaz.")

    ws = c.get("warnings") or []
    if ws:
        parts.append("Dikkat: " + " ".join(warning_text(w) for w in ws))
    return "\n\n".join(parts)


def interpret_object(c: dict) -> str:
    oa = (c.get("objects") or {}).get("a") or {}
    ob = (c.get("objects") or {}).get("b") or {}
    va, vb, ch = c.get("a_view") or {}, c.get("b_view") or {}, c.get("channel") or {}
    parts = [
        f"Bu cisim–cisim karşılaştırması {oa.get('name') or '?'} ile {ob.get('name') or '?'} arasında"
        + (f", D{va['detector']} dedektöründe" if va.get("detector") else "")
        + f" (λ ≈ {num(va.get('wavelength_um'), 3)} / {num(vb.get('wavelength_um'), 3)} µm)."
    ]
    ta, tb = oa.get("otype_desc") or oa.get("otype"), ob.get("otype_desc") or ob.get("otype")
    if ta or tb:
        same = c.get("same_type")
        parts.append(
            f"Türler (SIMBAD): {ta or 'bilinmiyor'} / {tb or 'bilinmiyor'}"
            + (
                " — aynı tür."
                if same
                else " — farklı türler; karşılaştırma yalnızca görünüm amaçlı."
                if ta and tb
                else "."
            )
        )
    if ch.get("status"):
        parts.append(f"Kanal: {CHANNEL_TEXT.get(ch['status'], ch['status']).lower()}.")
    da, db = (oa.get("distance") or {}).get("pc"), (ob.get("distance") or {}).get("pc")
    if da or db:
        parts.append(f"Uzaklık (SIMBAD paralaksı): {num(da)} pc / {num(db)} pc.")
    fa, fb = (va.get("photometry") or {}), (vb.get("photometry") or {})
    if fa.get("flux_ujy") is not None or fb.get("flux_ujy") is not None:
        s = (
            f"SPHEREx akısı: {num(fa.get('flux_ujy'), 0)} ± {num(fa.get('err_ujy'), 0)} µJy "
            f"(AB {num(va.get('ab_mag'))}) / {num(fb.get('flux_ujy'), 0)} ± {num(fb.get('err_ujy'), 0)} µJy "
            f"(AB {num(vb.get('ab_mag'))})."
        )
        r = c.get("flux_ratio_b_over_a")
        if r:
            s += f" Bu kanalda B, A'dan {num(r, 2)} kat {'parlak' if r >= 1 else 'sönük'}."
        parts.append(s)
    else:
        parts.append("Bu kanalda iki cismin akısı da ölçülemedi.")
    ws = c.get("warnings") or []
    if ws:
        parts.append("Dikkat: " + " ".join(warning_text(w) for w in ws))
    return "\n\n".join(parts)


def describe_object(obj: dict | None, info: dict | None) -> str | None:
    if not obj:
        return None
    name = obj.get("name") or "Seçili cisim"
    if obj.get("kind") == "solar_system":
        bits = [f"{name} bir Güneş Sistemi cismi"]
        if obj.get("orbit_class"):
            bits.append(f"(yörünge sınıfı: {obj['orbit_class']}, JPL SBDB)")
        return (
            " ".join(bits)
            + ". Konumu her gün değiştiği için site IRSA MOST ile her SPHEREx karesindeki öngörülen konumu "
            "kullanır; kareleri kare kare oynatabilirsin."
        )
    if obj.get("kind") == "coordinate":
        return (
            f"Seçili hedef bir koordinat ({name}); katalog bilgisi yok. "
            "SPHEREx görüntüleri bu konum için listelenir."
        )
    sim = (info or {}).get("simbad") or {}
    parts = []
    t = sim.get("otype_desc") or sim.get("otype")
    head = f"{name}" + (f": {t}" if t else "")
    if sim.get("sp_type"):
        head += f", tayf türü {sim['sp_type']}"
    parts.append(head + " (SIMBAD).")
    dist = (info or {}).get("distance")
    if dist:
        parts.append(
            f"Uzaklık yaklaşık {num(dist.get('ly'), 1)} ışık yılı "
            f"({num(dist.get('pc'), 2)} pc; {dist.get('method')})."
        )
    pmra, pmdec = sim.get("pmra_mas_yr"), sim.get("pmdec_mas_yr")
    if pmra is not None and pmdec is not None:
        pm = (pmra**2 + pmdec**2) ** 0.5
        parts.append(f"Öz hareketi yılda {num(pm / 1000, 2)}″ (SIMBAD).")
    wk = (info or {}).get("wikipedia") or {}
    if wk.get("extract"):
        sentences = re.split(r"(?<=[.!?])\s+", wk["extract"].strip())
        parts.append(" ".join(sentences[:2]) + f" (Vikipedi, {wk.get('lang', '?')})")
    if not info:
        parts.append("Ayrıntılı bilgi şu an alınamadı; bilgi panelinde tekrar deneyebilirsin.")
    return " ".join(parts)


# ---------- the rule-based engine ----------

Resolver = Callable[[str], Awaitable[dict | None]]


class RuleBasedAssistant:
    def __init__(self, resolve: Resolver | None = None):
        self._resolve = resolve  # optional remote name resolution for short messages

    async def answer(self, message: str | None, quick: str | None, ctx: Context) -> Answer:
        data = faq()
        if quick:
            entry = data["_by_id"].get(quick)
            if entry is None:
                return self._fallback()
            return self._entry_answer(entry, ctx)

        text = (message or "").strip()[:MAX_MESSAGE]
        norm = names.normalize(text)
        if not norm:
            return self._fallback()
        if _GREETING.match(norm) and len(norm.split()) <= 3:
            return Answer(data["greeting"], "greeting", _suggest(["site", "howto", "spherex"]))

        ranked = score(text)
        best = ranked[0] if ranked else None
        mention = names.find_in_text(text)
        if mention and (best is None or best[0] < data["min_score"] + 2):
            return Answer(
                f"{mention['name']} açılıyor…",
                "open_object",
                _suggest(["object", "howto"]),
                {"type": "open_object", "q": mention["query"]},
            )
        if best and best[0] >= data["min_score"]:
            return self._entry_answer(best[1], ctx)
        if self._resolve and len(norm.split()) <= 5:
            try:
                target = await self._resolve(text)
            except Exception:  # noqa: BLE001 - resolution is a convenience here
                target = None
            if target:
                return Answer(
                    f"{target.get('name') or text} açılıyor…",
                    "open_object",
                    _suggest(["object", "howto"]),
                    {"type": "open_object", "q": target.get("query") or text},
                )
        return self._fallback()

    def _fallback(self) -> Answer:
        data = faq()
        return Answer(data["fallback"], "fallback", _suggest(data["suggest_after_fallback"]))

    def _entry_answer(self, e: dict, ctx: Context) -> Answer:
        related = _suggest(e.get("related") or [])
        if e.get("dynamic") == "interpret" and ctx.comparison:
            c = ctx.comparison
            text = interpret_object(c) if c.get("kind") == "object" else interpret_time(c)
            return Answer(text, "interpret", related)
        if e.get("dynamic") == "object":
            d = describe_object(ctx.object, ctx.object_info)
            if d:
                return Answer(d, "object", _suggest(["interpret", "howto"]))
        return Answer(e["answer"], f"faq:{e['id']}", related)

    async def reply(
        self, message: str | None, quick: str | None, ctx: Context
    ) -> AsyncIterator[str | Answer]:
        ans = await self.answer(message, quick, ctx)
        for piece in chunks(ans.text):
            yield piece
        yield ans


def chunks(text: str, words_per_chunk: int = 4) -> list[str]:
    """Split into small pieces that concatenate back to exactly `text` (whitespace kept)."""
    tokens = re.findall(r"\S+\s*|\s+", text)
    return ["".join(tokens[i : i + words_per_chunk]) for i in range(0, len(tokens), words_per_chunk)]


def engine_from_settings() -> AssistantEngine:
    from ..api.v1.resolve import resolve_target

    return RuleBasedAssistant(resolve=resolve_target)


def to_json(a: Answer) -> dict[str, Any]:
    return {"text": a.text, "source": a.source, "suggestions": a.suggestions, "action": a.action}
