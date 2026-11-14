import { GitCompareArrows, Image as ImageIcon, Info, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import CutoutView, { decodeCutout, type DecodedCutout } from "../components/CutoutView";
import ExcelButton from "../components/ExcelButton";
import ObsFilterBar from "../components/ObsFilterBar";
import QualityLine from "../components/QualityLine";
import ProgressLine from "../components/ProgressLine";
import SaveButton from "../components/SaveButton";
import {
  ApiError,
  apiPost,
  type CutoutResult,
  type ObservationImage,
  type ObservationsResult,
  type Target,
} from "../lib/api";
import { BANDS } from "../lib/bands";
import { errorText, fmt, raDecText } from "../lib/format";
import { runJob, type ProgressStep } from "../lib/jobs";
import { lastComparison } from "../lib/lastComparison";
import { NO_FILTERS, passes, toExport, type ObsFilters } from "../lib/obsFilters";
import { percentileLimits, type Colormap, type Stretch } from "../render/image";
import CompareView, { ViewControls } from "./CompareView";
import type { TimeCompareResult } from "./compareTypes";
import MovingView from "./MovingView";
import NeossatPanel from "./NeossatPanel";
import ObjectCompare from "./ObjectCompare";
import ResultPanel from "./ResultPanel";
import SpectrumPanel from "./SpectrumPanel";

const SIZES = [0.05, 0.1, 0.25, 0.5];

function usable(images: ObservationImage[]) {
  return images.filter((i) => i.wavelength_um !== null && i.on_detector);
}

function closest(images: ObservationImage[], lam: number) {
  return usable(images).reduce<ObservationImage | null>(
    (best, i) =>
      best === null || Math.abs(i.wavelength_um! - lam) < Math.abs(best.wavelength_um! - lam) ? i : best,
    null,
  );
}

/** Client-side preview of decision S5 (the server re-checks with the exact cutout wavelengths). */
function channelStatus(a: ObservationImage | null, b: ObservationImage | null) {
  if (!a?.wavelength_um || !b?.wavelength_um) return null;
  const bw = ((a.bandwidth_um ?? 0) + (b.bandwidth_um ?? 0)) / 2;
  const ratio = Math.abs(a.wavelength_um - b.wavelength_um) / (bw || 1);
  return {
    ratio,
    dl: (b.wavelength_um - a.wavelength_um) * 1000,
    status: ratio <= 0.5 ? "match" : ratio <= 1 ? "warn" : "reject",
  };
}

/** Default pair: the exposure in visit A whose closest partner in visit B has the smallest Δλ/bandwidth. */
function bestPair(imagesA: ObservationImage[], imagesB: ObservationImage[]) {
  let best: { a: ObservationImage; b: ObservationImage; r: number } | null = null;
  for (const a of usable(imagesA)) {
    const b = closest(imagesB, a.wavelength_um!);
    const r = channelStatus(a, b)?.ratio ?? Infinity;
    if (b && (best === null || r < best.r)) best = { a, b, r };
  }
  return best;
}

const URL_PARAMS = new URLSearchParams(window.location.search);

/** Data-quality line of one cutout (decodeCutout keeps the whole server response in `raw`). */
function singleQuality(t: TFunction, c: CutoutResult): string[] {
  return [
    t("quality.masked", { pct: fmt(c.meta.bad_fraction * 100, 1) }),
    c.meta.zodi === "sub" ? t("quality.zodiSub", { model: c.meta.zodi_model ?? "?" }) : t("quality.zodiRaw"),
    t("quality.pipeline", { v: c.meta.pipeline_version ?? "?", rel: c.release.toUpperCase() }),
  ];
}

/** Data-quality line of a time comparison: masked share per epoch and every correction applied. */
function compareQuality(t: TFunction, r: TimeCompareResult): string[] {
  const out = [
    t("quality.maskedAB", { a: fmt(r.a.bad_fraction * 100, 1), b: fmt(r.b.bad_fraction * 100, 1) }),
    r.zodi === "sub" ? t("quality.zodiSubShort") : t("quality.zodiRaw"),
  ];
  if (r.background.a !== null && r.background.b !== null) out.push(t("quality.background"));
  out.push(
    r.normalization.factor
      ? t("quality.normalized", { k: fmt(r.normalization.factor, 3) })
      : t("quality.notNormalized"),
  );
  if (r.flux_corrected_image) out.push(t("quality.fluxCorrected"));
  if (r.warnings.some((w) => w.code === "PROPER_MOTION_APPLIED")) out.push(t("quality.properMotion"));
  return out;
}

export default function Workspace({ target }: { target: Target }) {
  const { t } = useTranslation();
  const [detector, setDetector] = useState(() => {
    const d = Number(URL_PARAMS.get("d"));
    return d >= 1 && d <= 6 ? d : 2;
  });
  const autoCompare = useRef(URL_PARAMS.get("compare") === "1");
  const [obs, setObs] = useState<ObservationsResult | null>(null);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [visitA, setVisitA] = useState(0);
  const [visitB, setVisitB] = useState(0);
  const [imgA, setImgA] = useState<string | null>(null);
  const [imgB, setImgB] = useState<string | null>(null);
  const [size, setSize] = useState(0.1);
  const [zodi, setZodi] = useState(true);
  const [normalize, setNormalize] = useState(true);
  const [busy, setBusy] = useState<"view" | "compare" | null>(null);
  const [single, setSingle] = useState<DecodedCutout | null>(null);
  const [result, setResult] = useState<TimeCompareResult | null>(null);
  const [stretch, setStretch] = useState<Stretch>("asinh");
  const [cmap, setCmap] = useState<Colormap>("inferno");
  const [filters, setFilters] = useState<ObsFilters>(NO_FILTERS);
  // "Görüntü bilgisi bulunamadı": the server re-indexes by itself; if it still fails, redo the search
  // once without showing an error, keep the chosen pair and repeat the action
  const [reload, setReload] = useState(0);
  const retried = useRef(false);
  const pendingView = useRef(false);
  const keepPair = useRef<{ a: string | null; b: string | null } | null>(null);

  const progressText = (s: ProgressStep) => t(`workspace.progress.${s.step}`, { ...s, defaultValue: s.step });

  const retryOnce = (e: unknown, action: "view" | "compare") => {
    if (!(e instanceof ApiError) || e.code !== "UNKNOWN_IMAGE" || retried.current) return false;
    retried.current = true;
    keepPair.current = { a: imgA, b: imgB };
    if (action === "compare") autoCompare.current = true;
    else pendingView.current = true;
    setStep(t("workspace.progress.research"));
    setReload((n) => n + 1);
    return true;
  };

  // Observations (coverage + wavelength at the target) whenever the target or detector changes
  useEffect(() => {
    // State is reset by changeDetector() and by the parent remounting per target (key)
    if (target.ra === undefined || target.dec === undefined) return;
    const ctrl = new AbortController();
    runJob<ObservationsResult>(
      () =>
        apiPost("/sky/observations", { ra: target.ra, dec: target.dec, detector, object_key: target.key }),
      (s) => setStep(progressText(s)),
      ctrl.signal,
    )
      .then((r) => {
        setObs(r);
        if (!r.visits.length) return;
        // After a silent re-search keep the user's pair if both exposures still exist
        const keep = keepPair.current;
        keepPair.current = null;
        const where = (id: string | null) =>
          r.visits.findIndex((v) => v.images.some((i) => i.image_id === id));
        if (keep && where(keep.a) >= 0 && where(keep.b) >= 0) {
          setVisitA(where(keep.a));
          setVisitB(where(keep.b));
          setImgA(keep.a);
          setImgB(keep.b);
          return;
        }
        const a = 0;
        const b = r.visits.length - 1;
        setVisitA(a);
        setVisitB(b);
        const pair = bestPair(r.visits[a].images, r.visits[b].images);
        setImgA(pair?.a.image_id ?? null);
        setImgB(pair?.b.image_id ?? null);
      })
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setError(errorText(t, e));
      })
      .finally(() => setStep(null));
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.key, target.ra, target.dec, detector, reload]);

  const visits = obs?.visits ?? [];
  // Observation filters (date / release / λ): the lists show only passing exposures; Excel gets the same
  const imagesOf = (vi: number) => (visits[vi]?.images ?? []).filter((i) => passes(filters, i));
  const shownVisits = visits.map((v, i) => ({ v, i })).filter(({ i }) => imagesOf(i).length > 0);
  const shownCount = shownVisits.reduce((n, { i }) => n + imagesOf(i).length, 0);
  const totalCount = visits.reduce((n, v) => n + v.images.length, 0);
  const applyFilters = (f: ObsFilters) => {
    setFilters(f);
    if (!visits.length) return;
    const keep = (vi: number) => (visits[vi]?.images ?? []).filter((i) => passes(f, i));
    const idx = visits.map((_, i) => i).filter((i) => keep(i).length > 0);
    if (!idx.length) return;
    const va = idx.includes(visitA) ? visitA : idx[0];
    const vb = idx.includes(visitB) ? visitB : idx[idx.length - 1];
    setVisitA(va);
    setVisitB(vb);
    const pair = bestPair(keep(va), keep(vb));
    setImgA(pair?.a.image_id ?? usable(keep(va))[0]?.image_id ?? null);
    setImgB(pair?.b.image_id ?? null);
  };
  const a = useMemo(
    () => visits[visitA]?.images.find((i) => i.image_id === imgA) ?? null,
    [visits, visitA, imgA],
  );
  const b = useMemo(
    () => visits[visitB]?.images.find((i) => i.image_id === imgB) ?? null,
    [visits, visitB, imgB],
  );
  const ch = channelStatus(a, b);

  const changeDetector = (d: number) => {
    if (d === detector) return;
    const url = new URL(window.location.href);
    url.searchParams.set("d", String(d));
    window.history.replaceState(null, "", url);
    setObs(null);
    setError(null);
    setSingle(null);
    setResult(null);
    setDetector(d);
  };

  const pickA = (id: string) => {
    setImgA(id);
    const img = visits[visitA].images.find((i) => i.image_id === id);
    if (img?.wavelength_um) setImgB(closest(imagesOf(visitB), img.wavelength_um)?.image_id ?? null);
  };
  const pickVisitB = (v: number) => {
    setVisitB(v);
    if (a?.wavelength_um) setImgB(closest(imagesOf(v), a.wavelength_um)?.image_id ?? null);
  };
  const pickVisitA = (v: number) => {
    setVisitA(v);
    const list = usable(imagesOf(v));
    const pick = a?.wavelength_um ? closest(imagesOf(v), a.wavelength_um) : list[0];
    if (pick) {
      setImgA(pick.image_id);
      setImgB(closest(imagesOf(visitB), pick.wavelength_um!)?.image_id ?? null);
    }
  };

  const view = async () => {
    if (!a) return;
    setBusy("view");
    setError(null);
    setResult(null);
    try {
      const c = await runJob<CutoutResult>(
        () =>
          apiPost("/sky/cutout", {
            image_id: a.image_id,
            ra: target.ra,
            dec: target.dec,
            size_deg: size,
            zodi: zodi ? "sub" : "raw",
          }),
        (s) => setStep(progressText(s)),
      );
      setSingle(decodeCutout(c));
    } catch (e) {
      if (!retryOnce(e, "view")) setError(errorText(t, e));
    } finally {
      setBusy(null);
      setStep(null);
    }
  };

  const compare = async () => {
    if (!a || !b) return;
    setBusy("compare");
    setError(null);
    setSingle(null);
    try {
      const r = await runJob<TimeCompareResult>(
        () =>
          apiPost("/compare/time", {
            image_a: a.image_id,
            image_b: b.image_id,
            ra: target.ra,
            dec: target.dec,
            size_deg: size,
            zodi: zodi ? "sub" : "raw",
            normalize,
            main_id: target.main_id ?? null,
            object_key: target.key,
          }),
        (s) => setStep(progressText(s)),
      );
      setResult(r);
      lastComparison.set(r.id);
    } catch (e) {
      if (!retryOnce(e, "compare")) setError(errorText(t, e));
    } finally {
      setBusy(null);
      setStep(null);
    }
  };

  // Shareable link ?compare=1: run the comparison once the default pair is known
  useEffect(() => {
    if (pendingView.current && a) {
      pendingView.current = false; // repeat "Görüntüle (A)" after the silent re-search
      const id = window.setTimeout(() => void view(), 0);
      return () => window.clearTimeout(id);
    }
    if (!autoCompare.current || !a || !b || a.image_id === b.image_id) return;
    autoCompare.current = false;
    const id = window.setTimeout(() => void compare(), 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a, b]);

  const singleLimits = useMemo(
    () => (single ? percentileLimits([single.data]) : ([0, 1] as [number, number])),
    [single],
  );
  const sel =
    "h-10 w-full cursor-pointer rounded-lg border border-white/10 bg-space-950/70 px-2 text-sm text-ink-100";

  if (target.kind === "solar_system") return <MovingView target={target} />;

  return (
    <section className="space-y-4" aria-labelledby="ws-title">
      <div className="glass space-y-4 rounded-2xl p-5">
        <div>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 id="ws-title" className="font-display text-2xl font-semibold text-ink-100">
              {target.name}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <SaveButton
                kind="object"
                refId={target.key}
                label={target.name}
                data={{ q: target.kind === "coordinate" ? target.query : target.name, d: detector }}
              />
              <ExcelButton
                items={[{ q: target.kind === "coordinate" ? target.query : target.name, d: detector }]}
                filters={toExport(filters)}
              />
            </div>
          </div>
          <p className="font-mono text-sm text-ink-300">
            {raDecText(target.ra!, target.dec!)} · {target.otype ?? ""} · {target.source}
          </p>
          {target.moved_since_j2000_arcsec !== undefined && target.moved_since_j2000_arcsec > 1 && (
            <p className="mt-1 flex items-start gap-1.5 text-xs text-nebula-300">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {t("workspace.epochNote", {
                epoch: target.epoch,
                arcsec: fmt(target.moved_since_j2000_arcsec, 0),
              })}
            </p>
          )}
        </div>

        <fieldset>
          <legend className="mb-2 text-sm text-ink-300">{t("workspace.band")}</legend>
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5, 6].map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={detector === d}
                onClick={() => changeDetector(d)}
                className={`h-10 cursor-pointer rounded-lg px-3 text-sm transition-colors duration-200 ${
                  detector === d
                    ? "bg-nebula-500 text-white"
                    : "border border-white/10 text-ink-300 hover:text-ink-100"
                }`}
              >
                D{d} <span className="text-xs opacity-80">{BANDS[d]}</span>
              </button>
            ))}
          </div>
        </fieldset>

        {step && <ProgressLine text={step} />}
        {error && (
          <p className="text-sm text-danger-400" role="alert">
            {error}
          </p>
        )}
        {obs?.no_coverage && <p className="text-sm text-warn-400">{t("workspace.noCoverage")}</p>}

        {visits.length > 0 && (
          <>
            <p className="text-sm text-ink-300">
              {t("workspace.visits", { n: visits.length, total: obs?.total_images ?? 0 })}
            </p>
            <ObsFilterBar
              value={filters}
              onChange={applyFilters}
              releases={Object.entries(obs?.releases ?? {}).map(([id, r]) => ({ id, label: r.label }))}
              shown={shownCount}
              total={totalCount}
            />
            {shownVisits.length === 0 && <p className="text-sm text-warn-400">{t("filters.empty")}</p>}
            <div className="grid gap-4 md:grid-cols-2">
              {(["A", "B"] as const).map((which) => {
                const vi = which === "A" ? visitA : visitB;
                const cur = which === "A" ? imgA : imgB;
                return (
                  <div key={which} className="space-y-2 rounded-xl border border-white/10 p-3">
                    <p className="font-semibold text-ink-100">
                      {t(which === "A" ? "workspace.epochA" : "workspace.epochB")}
                    </p>
                    <label className="block text-xs text-ink-400">
                      {t("workspace.visit")}
                      <select
                        className={sel}
                        value={vi}
                        onChange={(e) => (which === "A" ? pickVisitA : pickVisitB)(Number(e.target.value))}
                      >
                        {shownVisits.map(({ v, i }) => (
                          <option key={v.label + i} value={i}>
                            {v.label} ({v.start} – {v.end}) · {v.releases.join("+").toUpperCase()}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-xs text-ink-400">
                      {t("workspace.exposure")}
                      <select
                        className={sel}
                        value={cur ?? ""}
                        onChange={(e) => (which === "A" ? pickA(e.target.value) : setImgB(e.target.value))}
                      >
                        {imagesOf(vi).map((i) => (
                          <option
                            key={i.image_id}
                            value={i.image_id}
                            disabled={!i.wavelength_um || !i.on_detector}
                          >
                            {i.wavelength_um
                              ? `${i.wavelength_um.toFixed(3)} µm`
                              : t("workspace.notOnDetector")}{" "}
                            · {i.date_obs.slice(0, 10)} · {i.release.toUpperCase()}
                          </option>
                        ))}
                      </select>
                    </label>
                    {which === "B" && <p className="text-xs text-ink-400">{t("workspace.auto")}</p>}
                  </div>
                );
              })}
            </div>

            <div className="flex flex-wrap items-end gap-4">
              {ch && (
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    ch.status === "match"
                      ? "bg-ok-400/15 text-ok-400"
                      : ch.status === "warn"
                        ? "bg-warn-400/15 text-warn-400"
                        : "bg-danger-400/15 text-danger-400"
                  }`}
                >
                  {t(`workspace.channelMatch.${ch.status}`)} ·{" "}
                  {t("workspace.deltaLambda", { dl: ch.dl.toFixed(1), ratio: ch.ratio.toFixed(2) })}
                </span>
              )}
              <label className="text-xs text-ink-400">
                {t("workspace.size")}
                <select
                  className={`${sel} w-28`}
                  value={size}
                  onChange={(e) => setSize(Number(e.target.value))}
                >
                  {SIZES.map((s) => (
                    <option key={s} value={s}>
                      {s}° ({Math.round(s * 60)}′)
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex h-10 items-center gap-2 text-sm text-ink-300">
                <input
                  type="checkbox"
                  checked={zodi}
                  onChange={(e) => setZodi(e.target.checked)}
                  className="size-4 accent-star-400"
                />
                {t("workspace.zodi")}
              </label>
              <label className="flex h-10 items-center gap-2 text-sm text-ink-300">
                <input
                  type="checkbox"
                  checked={normalize}
                  onChange={(e) => setNormalize(e.target.checked)}
                  className="size-4 accent-star-400"
                />
                {t("workspace.normalize")}
              </label>
              <div className="ml-auto flex gap-2">
                <button
                  type="button"
                  disabled={!a || busy !== null}
                  onClick={() => void view()}
                  className="flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-white/15 px-4 text-sm text-ink-100 hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy === "view" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <ImageIcon className="size-4" />
                  )}
                  {t("workspace.view")} (A)
                </button>
                <button
                  type="button"
                  disabled={!a || !b || busy !== null || ch?.status === "reject"}
                  onClick={() => void compare()}
                  className="flex h-10 cursor-pointer items-center gap-2 rounded-lg bg-star-400 px-4 text-sm font-semibold text-space-950 hover:bg-star-300 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy === "compare" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <GitCompareArrows className="size-4" />
                  )}
                  {t("workspace.compare")}
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {single && (
        <div className="glass space-y-3 rounded-2xl p-5">
          <ViewControls stretch={stretch} setStretch={setStretch} cmap={cmap} setCmap={setCmap} />
          <div className="mx-auto max-w-xl">
            <CutoutView
              cutout={single}
              limits={singleLimits}
              stretch={stretch}
              cmap={cmap}
              label={`A · ${single.raw.meta.date_obs.slice(0, 10)} · λ ${single.raw.meta.wavelength_um.toFixed(3)} µm`}
            />
          </div>
          {"wavelength_min_um" in single.raw.meta && (
            <p className="text-xs text-ink-400">
              {t("viewer.lambdaNote", {
                min: fmt((single.raw.meta as CutoutResult["meta"]).wavelength_min_um, 3),
                max: fmt((single.raw.meta as CutoutResult["meta"]).wavelength_max_um, 3),
                lam: fmt(single.raw.meta.wavelength_um, 3),
              })}
            </p>
          )}
          <QualityLine items={singleQuality(t, single.raw as unknown as CutoutResult)} />
        </div>
      )}

      {result && (
        <>
          <div className="glass space-y-3 rounded-2xl p-5">
            <CompareView result={result} />
            <QualityLine items={compareQuality(t, result)} />
          </div>
          <ResultPanel
            r={result}
            save={{
              label: `${target.name} · ${result.a.date_obs.slice(0, 10)} → ${result.b.date_obs.slice(0, 10)} · D${detector}`,
              data: { q: target.kind === "coordinate" ? target.query : target.name, d: detector },
            }}
          />
        </>
      )}

      {visits[visitA] && (
        <SpectrumPanel key={`${target.key}-${visits[visitA].index}`} target={target} visit={visits[visitA]} />
      )}
      {visits.length > 0 && <ObjectCompare target={target} imageA={imgA} size={size} zodi={zodi} />}
      {target.ra !== undefined && <NeossatPanel key={`neo-${target.key}`} target={target} />}
    </section>
  );
}
