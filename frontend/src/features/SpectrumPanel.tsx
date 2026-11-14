import { Activity, Loader2, Table2 } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import ProgressLine from "../components/ProgressLine";
import { apiPost, type Target } from "../lib/api";
import { errorText, fmt } from "../lib/format";
import { runJob } from "../lib/jobs";

export type SpectrumPoint = {
  image_id: string;
  detector: number;
  release: string;
  date_obs: string;
  wavelength_um: number;
  bandwidth_um: number | null;
  flux_ujy: number;
  err_ujy: number;
  masked_in_aperture: number | null;
};
export type SpectrumResult = {
  visit: { index: number; label: string; start: string; end: string } | null;
  points: SpectrumPoint[];
  counts: { exposures: number; ok?: number; no_photometry?: number; off_detector?: number; error?: number };
  method: string;
  unit: string;
};

// Nominal SPHEREx detector ranges (µm), same as the server's DETECTOR_RANGE_UM
const DETECTORS: [number, number, number][] = [
  [1, 0.7455, 1.1167],
  [2, 1.1033, 1.6499],
  [3, 1.6301, 2.4346],
  [4, 2.4027, 3.8473],
  [5, 3.8113, 4.43],
  [6, 4.4115, 5.0096],
];
const W = 640;
const H = 300;
const M = { l: 64, r: 12, t: 22, b: 40 };
const X0 = 0.7;
const X1 = 5.05;

function niceTicks(lo: number, hi: number, n = 5) {
  const step0 = (hi - lo) / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? step0;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(v);
  return out;
}

/** One series (the target's spectrum in this visit); detectors are shown as x-axis bands, not colors. */
export function SpectrumChart({ points, log }: { points: SpectrumPoint[]; log: boolean }) {
  const { t } = useTranslation();
  const [hover, setHover] = useState<number | null>(null);
  const pos = points.filter((p) => p.flux_ujy > 0);
  const shown = log ? pos : points;
  const lo = Math.min(...shown.map((p) => p.flux_ujy - (log ? 0 : p.err_ujy)));
  const hi = Math.max(...shown.map((p) => p.flux_ujy + p.err_ujy));
  const yLo = log ? Math.log10(Math.max(lo, hi * 1e-4)) : Math.min(0, lo);
  const yHi = log ? Math.log10(hi) + 0.05 : hi * 1.05;
  const fy = (v: number) => {
    const y = log ? Math.log10(Math.max(v, 10 ** yLo)) : v;
    return M.t + (1 - (y - yLo) / (yHi - yLo || 1)) * (H - M.t - M.b);
  };
  const fx = (l: number) => M.l + ((l - X0) / (X1 - X0)) * (W - M.l - M.r);
  const yTicks = log
    ? niceTicks(Math.ceil(yLo), Math.floor(yHi), Math.max(1, Math.floor(yHi) - Math.ceil(yLo))).map(
        (e) => 10 ** e,
      )
    : niceTicks(yLo, yHi);
  const hp = hover !== null ? shown[hover] : null;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={t("spectrum.title")}>
        {DETECTORS.map(([d, a, b], i) => (
          <g key={d}>
            <rect
              x={fx(a)}
              y={M.t}
              width={fx(b) - fx(a)}
              height={H - M.t - M.b}
              fill={i % 2 ? "rgb(255 255 255 / 0.035)" : "rgb(255 255 255 / 0.065)"}
            />
            <text
              x={(fx(a) + fx(b)) / 2}
              y={M.t - 7}
              textAnchor="middle"
              className="fill-ink-400 text-[11px]"
            >
              D{d}
            </text>
          </g>
        ))}
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={M.l} x2={W - M.r} y1={fy(v)} y2={fy(v)} stroke="rgb(255 255 255 / 0.08)" />
            <text x={M.l - 6} y={fy(v) + 4} textAnchor="end" className="fill-ink-400 text-[11px]">
              {v >= 1e4 ? `${fmt(v / 1000, 0)}k` : fmt(v, v < 10 ? 1 : 0)}
            </text>
          </g>
        ))}
        {[1, 2, 3, 4, 5].map((l) => (
          <text key={l} x={fx(l)} y={H - M.b + 16} textAnchor="middle" className="fill-ink-400 text-[11px]">
            {l}
          </text>
        ))}
        <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" className="fill-ink-300 text-[12px]">
          {t("spectrum.axisX")}
        </text>
        <text
          transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`}
          textAnchor="middle"
          className="fill-ink-300 text-[12px]"
        >
          {t("spectrum.axisY")}
        </text>
        {shown.map((p, i) => {
          const x = fx(p.wavelength_um);
          const bw = (p.bandwidth_um ?? 0) / 2;
          return (
            <g key={p.image_id}>
              <line
                x1={x}
                x2={x}
                y1={fy(p.flux_ujy - p.err_ujy)}
                y2={fy(p.flux_ujy + p.err_ujy)}
                stroke="#60a5fa"
                strokeOpacity={0.55}
                strokeWidth={1.5}
              />
              <line
                x1={fx(p.wavelength_um - bw)}
                x2={fx(p.wavelength_um + bw)}
                y1={fy(p.flux_ujy)}
                y2={fy(p.flux_ujy)}
                stroke="#60a5fa"
                strokeOpacity={0.55}
                strokeWidth={1.5}
              />
              <circle
                cx={x}
                cy={fy(p.flux_ujy)}
                r={hover === i ? 5 : 3.5}
                fill="#93c5fd"
                stroke="#050816"
                strokeWidth={1.5}
              />
              <circle
                cx={x}
                cy={fy(p.flux_ujy)}
                r={10}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                tabIndex={0}
                aria-label={t("spectrum.point", {
                  lam: fmt(p.wavelength_um, 3),
                  flux: fmt(p.flux_ujy, 0),
                  err: fmt(p.err_ujy, 0),
                  det: p.detector,
                  date: p.date_obs.slice(0, 10),
                })}
              />
            </g>
          );
        })}
      </svg>
      {hp && (
        <div
          className="glass-strong pointer-events-none absolute rounded-lg px-2.5 py-1.5 text-xs text-ink-100"
          style={{
            left: `${(fx(hp.wavelength_um) / W) * 100}%`,
            top: `${(fy(hp.flux_ujy) / H) * 100}%`,
            transform: `translate(${fx(hp.wavelength_um) > W * 0.7 ? "-105%" : "8%"}, -110%)`,
          }}
        >
          {t("spectrum.point", {
            lam: fmt(hp.wavelength_um, 3),
            flux: fmt(hp.flux_ujy, 0),
            err: fmt(hp.err_ujy, 0),
            det: hp.detector,
            date: hp.date_obs.slice(0, 10),
          })}
        </div>
      )}
    </div>
  );
}

export default function SpectrumPanel({
  target,
  visit,
}: {
  target: Target;
  visit: { index: number; label: string };
}) {
  const { t } = useTranslation();
  const titleId = useId();
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<SpectrumResult | null>(null);
  const [log, setLog] = useState(true);
  const [table, setTable] = useState(false);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await runJob<SpectrumResult>(
        () =>
          apiPost("/sky/spectrum", {
            ra: target.ra,
            dec: target.dec,
            visit: visit.index,
            object_key: target.key,
          }),
        (s) =>
          setStep(
            t(`spectrum.${s.step === "spectrum_start" ? "start" : "progress"}`, {
              ...s,
              defaultValue: t(`workspace.progress.${s.step}`, { ...s, defaultValue: "" }),
            }),
          ),
      );
      setRes(r);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
      setStep(null);
    }
  };

  const counts = useMemo(() => res?.counts, [res]);
  return (
    <section className="glass space-y-3 rounded-2xl p-5" aria-labelledby={titleId}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={titleId} className="flex items-center gap-2 font-display text-lg font-semibold text-ink-100">
          <Activity className="size-5 text-nebula-300" aria-hidden="true" />
          {t("spectrum.title")} · {visit.label}
        </h3>
        {!res && (
          <button
            type="button"
            onClick={() => void run()}
            disabled={busy}
            className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg bg-nebula-500 px-3 text-sm font-medium text-white hover:bg-nebula-600 disabled:cursor-wait disabled:opacity-70"
          >
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {t("spectrum.run")}
          </button>
        )}
      </div>
      {!res && <p className="text-sm text-ink-300">{t("spectrum.intro")}</p>}
      {step && <ProgressLine text={step} />}
      {error && (
        <p className="text-sm text-danger-400" role="alert">
          {error}
        </p>
      )}
      {res && (
        <>
          {res.points.length === 0 ? (
            <p className="text-sm text-warn-400">{t("spectrum.none")}</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <label className="inline-flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={log}
                    onChange={(e) => setLog(e.target.checked)}
                    className="size-4 accent-nebula-500"
                  />
                  {t("spectrum.log")}
                </label>
                <button
                  type="button"
                  onClick={() => setTable((v) => !v)}
                  aria-pressed={table}
                  className="inline-flex cursor-pointer items-center gap-1.5 text-nebula-300 hover:underline"
                >
                  <Table2 className="size-4" aria-hidden="true" />
                  {t("spectrum.table")}
                </button>
              </div>
              {table ? (
                <div className="max-h-72 overflow-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-ink-400">
                      <tr>
                        <th className="py-1 pr-3">λ (µm)</th>
                        <th className="py-1 pr-3">{t("spectrum.axisY")}</th>
                        <th className="py-1 pr-3">±</th>
                        <th className="py-1 pr-3">{t("spectrum.detector")}</th>
                        <th className="py-1">{t("spectrum.date")}</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono text-ink-100">
                      {res.points.map((p) => (
                        <tr key={p.image_id} className="border-t border-white/5">
                          <td className="py-1 pr-3">{fmt(p.wavelength_um, 4)}</td>
                          <td className="py-1 pr-3">{fmt(p.flux_ujy, 0)}</td>
                          <td className="py-1 pr-3">{fmt(p.err_ujy, 0)}</td>
                          <td className="py-1 pr-3">D{p.detector}</td>
                          <td className="py-1">{p.date_obs.slice(0, 10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <SpectrumChart points={res.points} log={log} />
              )}
            </>
          )}
          {counts && (
            <p className="text-xs text-ink-400">
              {t("spectrum.counts", {
                ok: counts.ok ?? 0,
                no_photometry: counts.no_photometry ?? 0,
                off_detector: counts.off_detector ?? 0,
                error: counts.error ?? 0,
              })}
            </p>
          )}
          <p className="text-xs text-ink-400">{res.method}</p>
        </>
      )}
    </section>
  );
}
