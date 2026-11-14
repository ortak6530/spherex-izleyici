import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import CutoutView, { type DecodedCutout } from "../components/CutoutView";
import { track } from "../lib/events";
import { COLORMAPS, decodeFloat32, STRETCHES, type Colormap, type Stretch } from "../render/image";
import type { TimeCompareResult } from "./compareTypes";

type Mode = "side" | "swipe" | "blink" | "diff";
const MODES: Mode[] = ["side", "blink", "swipe", "diff"];

export function ViewControls({
  stretch,
  setStretch,
  cmap,
  setCmap,
}: {
  stretch: Stretch;
  setStretch: (s: Stretch) => void;
  cmap: Colormap;
  setCmap: (c: Colormap) => void;
}) {
  const { t } = useTranslation();
  const sel =
    "h-9 cursor-pointer rounded-lg border border-white/10 bg-space-950/70 px-2 text-sm text-ink-100";
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-ink-300">
      <label className="flex items-center gap-2">
        {t("viewer.stretch")}
        <select className={sel} value={stretch} onChange={(e) => setStretch(e.target.value as Stretch)}>
          {STRETCHES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2">
        {t("viewer.colormap")}
        <select className={sel} value={cmap} onChange={(e) => setCmap(e.target.value as Colormap)}>
          {COLORMAPS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

export default function CompareView({ result }: { result: TimeCompareResult }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<Mode>("blink");
  const [stretch, setStretch] = useState<Stretch>("asinh");
  const [cmap, setCmap] = useState<Colormap>("inferno");
  const [showB, setShowB] = useState(false);
  const [rateMs, setRateMs] = useState(700);
  const [swipe, setSwipe] = useState(50);

  const { a, b, diff } = useMemo(
    () => ({
      a: decodeFloat32(result.a_b64),
      b: decodeFloat32(result.b_b64),
      diff: decodeFloat32(result.diff_b64),
    }),
    [result],
  );
  // Both epochs share A's sky grid, so overlays (N/E, scale bar, target) are valid for both
  const base = (data: Float32Array, date: string, lam: number): DecodedCutout => ({
    raw: {
      width: result.width,
      height: result.height,
      meta: {
        unit: "MJy/sr",
        target_px: result.a.target_px,
        wavelength_um: lam,
        date_obs: date,
        north_deg: result.orientation.north_deg,
        east_deg: result.orientation.east_deg,
        pixel_scale_arcsec: result.orientation.pixel_scale_arcsec,
      },
    },
    data,
    lambda: null,
  });
  const viewA = base(a, result.a.date_obs, result.a.wavelength_um);
  const viewB = base(b, result.b.date_obs, result.b.wavelength_um);
  const labelA = `A · ${result.a.date_obs.slice(0, 10)} · λ ${result.a.wavelength_um.toFixed(3)} µm · ${result.a.release.toUpperCase()}`;
  const labelB = `B · ${result.b.date_obs.slice(0, 10)} · λ ${result.b.wavelength_um.toFixed(3)} µm · ${result.b.release.toUpperCase()}`;

  useEffect(() => {
    if (mode !== "blink") return;
    const id = window.setInterval(() => setShowB((v) => !v), rateMs);
    return () => window.clearInterval(id);
  }, [mode, rateMs]);

  const [showTrack, setShowTrack] = useState(true);
  const common = {
    limits: result.shared_limits,
    stretch,
    cmap,
    track: showTrack ? (result.track ?? null) : null,
  };
  const tabCls = (m: Mode) =>
    `h-9 cursor-pointer rounded-lg px-3 text-sm transition-colors duration-200 ${
      mode === m ? "bg-nebula-500 text-white" : "border border-white/10 text-ink-300 hover:text-ink-100"
    }`;

  return (
    <section className="space-y-3" aria-label={t("result.title")}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" className="flex flex-wrap gap-2">
          {MODES.map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              className={tabCls(m)}
              onClick={() => {
                setMode(m);
                track("view_changed", { payload: { mode: m } });
              }}
            >
              {t(`viewer.modes.${m}`)}
            </button>
          ))}
        </div>
        {mode !== "diff" && (
          <ViewControls stretch={stretch} setStretch={setStretch} cmap={cmap} setCmap={setCmap} />
        )}
      </div>

      {mode === "side" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <CutoutView cutout={viewA} label={labelA} {...common} />
          <CutoutView cutout={viewB} label={labelB} {...common} />
        </div>
      )}

      {mode === "blink" && (
        <div className="mx-auto max-w-xl space-y-2">
          <CutoutView cutout={showB ? viewB : viewA} label={showB ? labelB : labelA} {...common} />
          <label className="flex items-center gap-3 text-sm text-ink-300">
            {t("viewer.blinkRate")}
            <input
              type="range"
              min={250}
              max={1500}
              step={50}
              value={1750 - rateMs}
              onChange={(e) => setRateMs(1750 - Number(e.target.value))}
              className="w-40 accent-star-400"
            />
          </label>
        </div>
      )}

      {mode === "swipe" && (
        <div className="mx-auto max-w-xl space-y-2">
          <p className="text-sm text-ink-100">
            ◧ {labelB} &nbsp;|&nbsp; {labelA} ◨
          </p>
          <div className="relative">
            <CutoutView cutout={viewA} {...common} />
            {/* B is stacked exactly on top of A and clipped from the right: left part = B, right part = A */}
            <div
              className="pointer-events-none absolute inset-0"
              style={{ clipPath: `inset(0 ${100 - swipe}% 0 0)` }}
            >
              <CutoutView cutout={viewB} {...common} />
            </div>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={swipe}
            aria-label={t("viewer.modes.swipe")}
            onChange={(e) => setSwipe(Number(e.target.value))}
            className="w-full accent-star-400"
          />
        </div>
      )}

      {mode === "diff" && (
        <div className="mx-auto max-w-xl space-y-2">
          <CutoutView
            cutout={base(diff, result.b.date_obs, result.b.wavelength_um)}
            label={`B − A${result.normalization.factor ? ` (B × ${result.normalization.factor.toFixed(3)})` : ""}`}
            limits={[-result.diff_limit, result.diff_limit]}
            stretch="linear"
            cmap="diverging"
            track={common.track}
          />
          <p className="text-xs text-ink-400">{t("viewer.diffLegend")}</p>
        </div>
      )}
      {mode !== "diff" && <p className="text-xs text-ink-400">{t("viewer.sharedScale")}</p>}
      {result.track && (
        <div className="space-y-1 text-xs text-ink-300">
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showTrack}
              onChange={(e) => setShowTrack(e.target.checked)}
              className="size-4 accent-nebula-500"
            />
            {t("viewer.track")}
          </label>
          {showTrack && (
            <p>
              {t("viewer.trackLegend")} {result.track.note} ({result.track.source})
            </p>
          )}
        </div>
      )}
    </section>
  );
}
