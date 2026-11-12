import { AlertTriangle, ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";

import { fmt, warningText } from "../lib/format";
import type { TimeCompareResult } from "./compareTypes";

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-space-950/50 p-3">
      <p className="text-xs text-ink-400">{label}</p>
      <p className="mt-1 font-mono text-sm text-ink-100">{children}</p>
    </div>
  );
}

export default function ResultPanel({ r }: { r: TimeCompareResult }) {
  const { t } = useTranslation();
  const ph = r.photometry;
  const chip = r.channel.status === "match" ? "bg-ok-400/15 text-ok-400" : "bg-warn-400/15 text-warn-400";

  return (
    <section className="glass space-y-4 rounded-2xl p-5" aria-labelledby="result-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="result-title" className="font-display text-lg font-semibold text-ink-100">
          {t("result.title")}
        </h3>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${chip}`}>
          {t(`workspace.channelMatch.${r.channel.status}`)} ·{" "}
          {t("workspace.deltaLambda", {
            dl: (r.channel.delta_um * 1000).toFixed(1),
            ratio: r.channel.ratio.toFixed(2),
          })}
        </span>
      </div>
      <p className="text-sm text-ink-300">{t("result.honest")}</p>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Stat label={t("result.shift")}>
          {r.shift
            ? t("result.shiftValue", {
                arcsec: fmt(r.shift.arcsec, 2),
                px: fmt(r.shift.px, 2),
                pa: fmt(r.shift.pa_deg, 0),
              })
            : t("result.noShift")}
        </Stat>
        {r.expected_shift && (
          <Stat label={`${t("result.expected")} (${r.expected_shift.source})`}>
            {fmt(r.expected_shift.arcsec, 2)}″ ({fmt(r.expected_shift.px, 2)} px)
          </Stat>
        )}
        <Stat label={t("result.brightness")}>
          {ph.change
            ? `${ph.change.percent >= 0 ? "+" : ""}${fmt(ph.change.percent, 1)} ± ${fmt(ph.change.err_percent, 1)} %`
            : t("result.noBrightness")}
          {ph.change_normalized && (
            <span className="block text-xs text-ink-400">
              {t("result.brightnessNorm")}: {fmt(ph.change_normalized.percent, 1)} ±{" "}
              {fmt(ph.change_normalized.err_percent, 1)} %
            </span>
          )}
        </Stat>
        <Stat label={t("result.dt")}>{t("result.days", { n: fmt(r.dt_days, 1) })}</Stat>
        <Stat label={t("result.normalization")}>
          {r.normalization.factor ? `× ${fmt(r.normalization.factor, 3)}` : "—"}
        </Stat>
        <Stat label={t("result.difference")}>
          {r.difference.n
            ? t("result.diffStats", {
                mean: fmt(r.difference.mean, 3),
                std: fmt(r.difference.std, 3),
                sigma: fmt(r.difference.max_sigma, 1),
              })
            : "—"}
        </Stat>
      </div>

      {r.warnings.length > 0 && (
        <div>
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-warn-400">
            <AlertTriangle className="size-4" aria-hidden="true" /> {t("result.warnings")}
          </h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-300">
            {r.warnings.map((w, i) => (
              <li key={`${w.code}-${i}`}>{warningText(t, w)}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap gap-4 text-xs text-ink-400">
        {[r.a, r.b].map((e, i) => (
          <a
            key={e.image_id}
            href={e.fits_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 text-nebula-300 hover:underline"
          >
            {i === 0 ? "A" : "B"}: {e.obs_id} D{e.detector} · {e.release.toUpperCase()} · v
            {e.pipeline_version} · {t("result.fits")}
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
        ))}
      </div>
    </section>
  );
}
