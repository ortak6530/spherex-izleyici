import { ChevronLeft, ChevronRight, ExternalLink, Info, Loader2, Pause, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import CutoutView, { decodeCutout, type DecodedCutout } from "../components/CutoutView";
import ProgressLine from "../components/ProgressLine";
import {
  apiGet,
  apiPost,
  type CutoutResult,
  type MovingFrame,
  type MovingResult,
  type Target,
} from "../lib/api";
import { BANDS } from "../lib/bands";
import { errorText, fmt, raDecText } from "../lib/format";
import { runJob, type ProgressStep } from "../lib/jobs";
import { percentileLimits, type Colormap, type Stretch } from "../render/image";
import { ViewControls } from "./CompareView";

const SIZES = [0.05, 0.1, 0.25];
const SPEEDS = [1, 2, 4];
const MAX_FRAMES = 40; // per visit + detector; the server rate limit allows ~40 quick requests
const PARALLEL = 3;
// CO2 (4.26 µm) is the strongest comet feature SPHEREx sees; D5 is the most telling default band.
const PREFERRED_DETECTOR = 5;
const TRACK_PAD_DAYS = 3;

type Slot = DecodedCutout | "error";
const slotKey = (f: MovingFrame, size: number, zodi: boolean) => `${f.image_id}|${size}|${zodi ? "s" : "r"}`;

/** Object path on the sky (whole ephemeris faint, this visit's frames highlighted, current frame marked). */
function TrackPlot({
  track,
  frames,
  current,
}: {
  track: MovingResult["track"];
  frames: MovingFrame[];
  current: MovingFrame | null;
}) {
  const { t } = useTranslation();
  // Only the part of the path around this visit; the whole mission path would squeeze it into a dot
  const near = useMemo(() => {
    if (!frames.length) return track;
    const lo = Math.min(...frames.map((f) => f.mjd)) - TRACK_PAD_DAYS;
    const hi = Math.max(...frames.map((f) => f.mjd)) + TRACK_PAD_DAYS;
    return track.filter((p) => p.mjd >= lo && p.mjd <= hi);
  }, [track, frames]);
  const geo = useMemo(() => {
    const pts = [...near.map((p) => [p.ra, p.dec]), ...frames.map((f) => [f.ra, f.dec])];
    if (!pts.length) return null;
    // Unwrap RA around the first point so a path crossing 0h stays continuous
    const ra0 = pts[0][0];
    const unwrap = (ra: number) => ra0 + ((((ra - ra0 + 180) % 360) + 360) % 360) - 180;
    const decs = pts.map((p) => p[1]);
    const cosd = Math.cos((((Math.min(...decs) + Math.max(...decs)) / 2) * Math.PI) / 180) || 1;
    // East to the left, as on the sky
    const xy = (ra: number, dec: number) => [-unwrap(ra) * cosd, -dec] as const;
    const all = pts.map((p) => xy(p[0], p[1]));
    const xs = all.map((p) => p[0]);
    const ys = all.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const span = Math.max(x1 - x0, y1 - y0, 1e-3);
    const pad = span * 0.08;
    return { xy, vb: `${x0 - pad} ${y0 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}`, s: span / 100 };
  }, [near, frames]);
  if (!geo) return null;
  const path = near.map((p, i) => `${i ? "L" : "M"}${geo.xy(p.ra, p.dec).join(",")}`).join(" ");
  const cur = current ? geo.xy(current.ra, current.dec) : null;
  return (
    <figure className="space-y-1">
      <svg
        viewBox={geo.vb}
        className="aspect-[4/3] w-full rounded-xl border border-white/10 bg-space-950/70"
        role="img"
        aria-label={t("moving.trackLabel")}
        preserveAspectRatio="xMidYMid meet"
      >
        <path d={path} fill="none" stroke="#7c86a8" strokeWidth={geo.s * 0.6} strokeOpacity={0.6} />
        {frames.map((f) => {
          const [x, y] = geo.xy(f.ra, f.dec);
          return <circle key={f.image_id} cx={x} cy={y} r={geo.s * 1.2} fill="#a78bfa" />;
        })}
        {cur && (
          <circle cx={cur[0]} cy={cur[1]} r={geo.s * 3} fill="none" stroke="#fcd34d" strokeWidth={geo.s} />
        )}
      </svg>
      <figcaption className="text-xs text-ink-400">{t("moving.trackCaption")}</figcaption>
    </figure>
  );
}

export default function MovingView({ target }: { target: Target }) {
  const { t } = useTranslation();
  const [res, setRes] = useState<MovingResult | null>(null);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [visitIdx, setVisitIdx] = useState(0);
  const [detector, setDetector] = useState(PREFERRED_DETECTOR);
  const [size, setSize] = useState(0.1);
  const [zodi, setZodi] = useState(true);
  const [commonScale, setCommonScale] = useState(false);
  const [stretch, setStretch] = useState<Stretch>("asinh");
  const [cmap, setCmap] = useState<Colormap>("inferno");
  const [slots, setSlots] = useState<Record<string, Slot>>({});
  const slotsRef = useRef(slots);
  useEffect(() => {
    slotsRef.current = slots;
  }, [slots]);
  const [loading, setLoading] = useState(false);
  const [pos, setPos] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState(2);

  const designation = target.designation ?? "";
  const progressText = (s: ProgressStep) => t(`moving.progress.${s.step}`, { ...s, defaultValue: s.step });

  // 1) Frames from MOST
  useEffect(() => {
    if (!designation) return;
    const ctrl = new AbortController();
    runJob<MovingResult>(
      () => apiGet(`/moving/${encodeURIComponent(designation)}/frames`),
      (s) => setStep(progressText(s)),
      ctrl.signal,
    )
      .then((r) => {
        setRes(r);
        if (!r.visits.length) return;
        // Default: the visit in which the object is predicted to be brightest (lowest V), so the first
        // thing people see has the best chance of showing it; ties -> more frames.
        const bright = (v: MovingResult["visits"][number]) => {
          const ids = new Set(v.frame_ids);
          const mags = r.frames.filter((f) => ids.has(f.image_id) && f.vmag !== null).map((f) => f.vmag!);
          return mags.length ? Math.min(...mags) : Infinity;
        };
        const best = r.visits.reduce(
          (b, v, i) =>
            bright(v) < bright(r.visits[b]) ||
            (bright(v) === bright(r.visits[b]) && v.frame_ids.length > r.visits[b].frame_ids.length)
              ? i
              : b,
          0,
        );
        setVisitIdx(best);
        if (!r.visits[best].frames_per_detector[PREFERRED_DETECTOR]) {
          const d = Object.entries(r.visits[best].frames_per_detector).sort((a, b) => b[1] - a[1])[0];
          if (d) setDetector(Number(d[0]));
        }
      })
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setError(errorText(t, e));
      })
      .finally(() => setStep(null));
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [designation]);

  const visit = res?.visits[visitIdx] ?? null;
  const selection = useMemo(() => {
    if (!res || !visit) return [];
    const ids = new Set(visit.frame_ids);
    return res.frames.filter((f) => ids.has(f.image_id) && f.detector === detector).slice(0, MAX_FRAMES);
  }, [res, visit, detector]);
  const selKey = selection.map((f) => f.image_id).join(",");

  // 2) Object-centred cutouts for the selection, a few at a time; shown as they arrive
  useEffect(() => {
    if (!selection.length) return;
    const ctrl = new AbortController();
    const todo = selection.filter((f) => slotsRef.current[slotKey(f, size, zodi)] === undefined);
    if (!todo.length) return;
    let next = 0;
    const worker = async () => {
      while (next < todo.length && !ctrl.signal.aborted) {
        const f = todo[next++];
        const k = slotKey(f, size, zodi);
        try {
          const c = await runJob<CutoutResult>(
            () =>
              apiPost("/moving/cutout", {
                image_id: f.image_id,
                ra: f.ra,
                dec: f.dec,
                size_deg: size,
                zodi: zodi ? "sub" : "raw",
              }),
            undefined,
            ctrl.signal,
          );
          if (!ctrl.signal.aborted) setSlots((m) => ({ ...m, [k]: decodeCutout(c) }));
        } catch {
          if (!ctrl.signal.aborted) setSlots((m) => ({ ...m, [k]: "error" }));
        }
      }
    };
    setLoading(true);
    void Promise.all(Array.from({ length: PARALLEL }, worker)).finally(() => {
      if (!ctrl.signal.aborted) setLoading(false);
    });
    return () => {
      ctrl.abort();
      setLoading(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selKey, size, zodi]);

  const slotOf = (f: MovingFrame | undefined) => (f ? slots[slotKey(f, size, zodi)] : undefined);
  const loaded = selection.filter((f) => {
    const s = slotOf(f);
    return s !== undefined && s !== "error";
  }).length;
  const failed = selection.filter((f) => slotOf(f) === "error").length;

  const current = selection[Math.min(pos, Math.max(selection.length - 1, 0))] ?? null;
  const slot = slotOf(current ?? undefined);
  const cut = slot && slot !== "error" ? slot : null;

  // Next/previous frame that has an image (skips frames still loading or failed)
  const step1 = (dir: 1 | -1) =>
    setPos((p) => {
      const n = selection.length;
      for (let i = 1; i <= n; i++) {
        const q = (((p + dir * i) % n) + n) % n;
        const s = slotOf(selection[q]);
        if (s && s !== "error") return q;
      }
      return p;
    });

  useEffect(() => {
    if (!playing || loaded < 2) return;
    const id = window.setInterval(() => step1(1), 1000 / fps);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, fps, loaded, selKey, size, zodi]);

  const commonLimits = useMemo(() => {
    const arrays = selection
      .map((f) => slots[slotKey(f, size, zodi)])
      .filter((s): s is DecodedCutout => !!s && s !== "error")
      .map((s) => s.data);
    return arrays.length ? percentileLimits(arrays) : null;
  }, [selection, slots, size, zodi]);
  const frameLimits = useMemo(
    () => (cut ? percentileLimits([cut.data]) : ([0, 1] as [number, number])),
    [cut],
  );
  const limits = commonScale && commonLimits ? commonLimits : frameLimits;

  const resetPlayback = () => {
    setPos(0);
    setPlaying(false);
  };
  const sel =
    "h-10 w-full cursor-pointer rounded-lg border border-white/10 bg-space-950/70 px-2 text-sm text-ink-100";
  const releaseLabel = (id: string) => id.toUpperCase();

  return (
    <section className="space-y-4" aria-labelledby="mv-title">
      <div className="glass space-y-4 rounded-2xl p-5">
        <div>
          <h2 id="mv-title" className="font-display text-2xl font-semibold text-ink-100">
            {target.name}
          </h2>
          <p className="text-sm text-ink-300">
            {[target.orbit_class, designation && `${t("moving.designation")}: ${designation}`, target.source]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="mt-1 flex items-start gap-1.5 text-xs text-nebula-300">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {t("moving.intro")}
          </p>
        </div>

        {!designation && <p className="text-sm text-warn-400">{t("moving.noDesignation")}</p>}
        {step && <ProgressLine text={step} />}
        {error && (
          <p className="text-sm text-danger-400" role="alert">
            {error}
          </p>
        )}
        {res && !res.frames.length && (
          <p className="text-sm text-warn-400">{t("moving.noFrames", { start: res.start, end: res.end })}</p>
        )}

        {res && visit && (
          <>
            <p className="text-sm text-ink-300">
              {t("moving.summary", {
                count: res.frames.length,
                visits: res.visits.length,
                releases: [...new Set(res.frames.map((f) => releaseLabel(f.release)))].join(", "),
              })}
            </p>
            <fieldset>
              <legend className="mb-2 text-sm text-ink-300">{t("moving.visit")}</legend>
              <div className="flex flex-wrap gap-2">
                {res.visits.map((v, i) => (
                  <button
                    key={v.index}
                    type="button"
                    aria-pressed={visitIdx === i}
                    onClick={() => {
                      setVisitIdx(i);
                      resetPlayback();
                    }}
                    className={`h-10 cursor-pointer rounded-lg px-3 text-sm transition-colors duration-200 ${
                      visitIdx === i
                        ? "bg-nebula-500 text-white"
                        : "border border-white/10 text-ink-300 hover:text-ink-100"
                    }`}
                  >
                    {v.start === v.end ? v.start : `${v.start} → ${v.end}`}
                    <span className="ml-1 text-xs opacity-80">
                      ({v.frame_ids.length} · {v.releases.map(releaseLabel).join("/")})
                    </span>
                  </button>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="mb-2 text-sm text-ink-300">{t("workspace.band")}</legend>
              <div className="flex flex-wrap gap-2">
                {[1, 2, 3, 4, 5, 6].map((d) => {
                  const n = visit.frames_per_detector[d] ?? 0;
                  return (
                    <button
                      key={d}
                      type="button"
                      disabled={!n}
                      aria-pressed={detector === d}
                      onClick={() => {
                        setDetector(d);
                        resetPlayback();
                      }}
                      className={`h-10 cursor-pointer rounded-lg px-3 text-sm transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
                        detector === d
                          ? "bg-nebula-500 text-white"
                          : "border border-white/10 text-ink-300 hover:text-ink-100"
                      }`}
                    >
                      D{d} <span className="text-xs opacity-80">{BANDS[d]}</span>{" "}
                      <span className="text-xs opacity-80">· {n}</span>
                    </button>
                  );
                })}
              </div>
            </fieldset>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="text-sm text-ink-300">
                {t("workspace.size")}
                <select className={sel} value={size} onChange={(e) => setSize(Number(e.target.value))}>
                  {SIZES.map((s) => (
                    <option key={s} value={s}>
                      {s}° ({Math.round(s * 60 * 10) / 10}′)
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 self-end pb-2 text-sm text-ink-300">
                <input type="checkbox" checked={zodi} onChange={(e) => setZodi(e.target.checked)} />
                {t("workspace.zodi")}
              </label>
              <label className="flex items-center gap-2 self-end pb-2 text-sm text-ink-300">
                <input
                  type="checkbox"
                  checked={commonScale}
                  onChange={(e) => setCommonScale(e.target.checked)}
                />
                {t("moving.commonScale")}
              </label>
            </div>
          </>
        )}
      </div>

      {res && visit && selection.length > 0 && (
        <div className="glass grid gap-5 rounded-2xl p-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div
            className="space-y-3"
            tabIndex={0}
            aria-label={t("moving.playerLabel")}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") step1(1);
              else if (e.key === "ArrowLeft") step1(-1);
              else if (e.key === " ") setPlaying((p) => !p);
              else return;
              e.preventDefault();
            }}
          >
            {cut ? (
              <CutoutView
                cutout={cut}
                limits={limits}
                stretch={stretch}
                cmap={cmap}
                label={t("moving.frameLabel", { n: pos + 1, total: selection.length })}
              />
            ) : (
              <div className="flex aspect-square w-full items-center justify-center rounded-xl border border-white/10 bg-space-950 text-sm text-ink-400">
                {slot === "error" ? (
                  t("moving.frameFailed")
                ) : (
                  <span className="flex items-center gap-2">
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" /> {t("moving.frameLoading")}
                  </span>
                )}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => step1(-1)}
                aria-label={t("moving.prev")}
                className="flex size-10 cursor-pointer items-center justify-center rounded-lg border border-white/10 text-ink-100 hover:bg-white/5"
              >
                <ChevronLeft className="size-5" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => setPlaying((p) => !p)}
                disabled={loaded < 2}
                aria-label={playing ? t("moving.pause") : t("moving.play")}
                className="flex h-10 cursor-pointer items-center gap-2 rounded-lg bg-nebula-500 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {playing ? (
                  <Pause className="size-4" aria-hidden="true" />
                ) : (
                  <Play className="size-4" aria-hidden="true" />
                )}
                {playing ? t("moving.pause") : t("moving.play")}
              </button>
              <button
                type="button"
                onClick={() => step1(1)}
                aria-label={t("moving.next")}
                className="flex size-10 cursor-pointer items-center justify-center rounded-lg border border-white/10 text-ink-100 hover:bg-white/5"
              >
                <ChevronRight className="size-5" aria-hidden="true" />
              </button>
              <label className="ml-auto flex items-center gap-2 text-sm text-ink-300">
                {t("moving.speed")}
                <select
                  className="h-9 cursor-pointer rounded-lg border border-white/10 bg-space-950/70 px-2 text-sm text-ink-100"
                  value={fps}
                  onChange={(e) => setFps(Number(e.target.value))}
                >
                  {SPEEDS.map((s) => (
                    <option key={s} value={s}>
                      {t("moving.fps", { n: s })}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block text-sm text-ink-300">
              <span className="sr-only">{t("moving.timeline")}</span>
              <input
                type="range"
                min={0}
                max={selection.length - 1}
                value={Math.min(pos, selection.length - 1)}
                onChange={(e) => setPos(Number(e.target.value))}
                className="w-full cursor-pointer accent-nebula-500"
                aria-valuetext={current ? current.date_obs.replace("T", " ").replace("Z", " UTC") : undefined}
              />
              <span className="flex justify-between font-mono text-xs text-ink-400">
                <span>{selection[0].date_obs.slice(0, 16).replace("T", " ")}</span>
                <span>{selection[selection.length - 1].date_obs.slice(0, 16).replace("T", " ")}</span>
              </span>
            </label>
            <p className="flex items-center gap-2 text-xs text-ink-400" role="status">
              {loading && <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />}
              {t("moving.loaded", { loaded, total: selection.length })}
              {failed > 0 && ` · ${t("moving.failed", { n: failed })}`}
              {visit.frames_per_detector[detector] > MAX_FRAMES &&
                ` · ${t("moving.capped", { n: MAX_FRAMES })}`}
            </p>
            <ViewControls stretch={stretch} setStretch={setStretch} cmap={cmap} setCmap={setCmap} />
          </div>

          <div className="space-y-4">
            {current && (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
                <dt className="text-ink-400">{t("moving.time")}</dt>
                <dd className="font-mono text-ink-100">
                  {current.date_obs.replace("T", " ").replace("Z", " UTC")}
                </dd>
                <dt className="text-ink-400">{t("moving.position")}</dt>
                <dd className="font-mono text-ink-100">{raDecText(current.ra, current.dec)}</dd>
                <dt className="text-ink-400">λ</dt>
                <dd className="font-mono text-ink-100">
                  {cut ? `${fmt(cut.raw.meta.wavelength_um, 3)} µm` : "—"}
                </dd>
                <dt className="text-ink-400">{t("moving.sunDist")}</dt>
                <dd className="font-mono text-ink-100">{fmt(current.sun_dist_au, 3)} AU</dd>
                <dt className="text-ink-400">{t("moving.geoDist")}</dt>
                <dd className="font-mono text-ink-100">{fmt(current.geo_dist_au, 3)} AU</dd>
                <dt className="text-ink-400">{t("moving.phase")}</dt>
                <dd className="font-mono text-ink-100">{fmt(current.phase_deg, 1)}°</dd>
                <dt className="text-ink-400">{t("moving.vmag")}</dt>
                <dd className="font-mono text-ink-100">{fmt(current.vmag, 1)}</dd>
                <dt className="text-ink-400">{t("moving.frame")}</dt>
                <dd className="font-mono text-xs break-all text-ink-100">
                  {releaseLabel(current.release)} · {current.obs_id} · D{current.detector}{" "}
                  <a
                    href={current.fits_url}
                    className="inline-flex items-center gap-1 text-nebula-300 underline-offset-2 hover:underline"
                    rel="noreferrer"
                  >
                    FITS <ExternalLink className="size-3" aria-hidden="true" />
                  </a>
                </dd>
              </dl>
            )}
            <TrackPlot track={res.track} frames={selection} current={current} />
            <p className="text-xs text-ink-400">{t("moving.notes")}</p>
            <p className="text-xs text-ink-400">{t("moving.source", { source: res.source })}</p>
          </div>
        </div>
      )}
    </section>
  );
}
