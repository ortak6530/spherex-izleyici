import { ExternalLink, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiGet, type ObjectInfo, type Target } from "../lib/api";
import { errorText, fmt, raDecText } from "../lib/format";

function Row({ label, value, source }: { label: string; value: React.ReactNode; source?: string }) {
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-2 border-b border-white/5 py-1.5 text-sm last:border-0">
      <dt className="text-ink-400">{label}</dt>
      <dd className="text-ink-100">
        {value}
        {source && <span className="ml-2 text-xs text-ink-400">[{source}]</span>}
      </dd>
    </div>
  );
}

export default function InfoPanel({ target }: { target: Target }) {
  const { t } = useTranslation();
  const [info, setInfo] = useState<ObjectInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mainId = target.main_id;

  useEffect(() => {
    // The parent remounts this panel per target (key), so no state reset is needed here
    if (!mainId) return;
    const ctrl = new AbortController();
    apiGet<ObjectInfo>(`/objects/info?main_id=${encodeURIComponent(mainId)}`, ctrl.signal)
      .then(setInfo)
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setError(errorText(t, e));
      });
    return () => ctrl.abort();
  }, [mainId, t]);

  const unknown = <span className="text-ink-400">{t("info.unknown")}</span>;
  const s = info?.simbad;
  const src = info?.sources.basic ?? "SIMBAD";

  return (
    <aside className="glass rounded-2xl p-5" aria-labelledby="info-title">
      <h2 id="info-title" className="font-display text-lg font-semibold text-ink-100">
        {t("info.title")}
      </h2>
      <p className="mt-1 text-sm text-ink-300">{target.name}</p>

      {target.kind === "coordinate" && (
        <dl className="mt-3">
          <Row
            label={t("info.coords")}
            value={raDecText(target.ra!, target.dec!)}
            source={t("search.label")}
          />
        </dl>
      )}
      {target.kind === "solar_system" && (
        <dl className="mt-3">
          <Row label={t("info.type")} value={target.orbit_class ?? unknown} source="JPL SBDB" />
        </dl>
      )}
      {mainId && !info && !error && (
        <p className="mt-4 flex items-center gap-2 text-sm text-ink-400">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" /> {t("info.loading")}
        </p>
      )}
      {error && <p className="mt-4 text-sm text-warn-400">{error}</p>}
      {info && (
        <>
          <dl className="mt-3">
            <Row
              label={t("info.type")}
              value={s?.otype ? `${s.otype_desc ?? s.otype_label ?? s.otype} (${s.otype})` : unknown}
              source={src}
            />
            <Row label={t("info.spType")} value={s?.sp_type ?? unknown} source={src} />
            {s?.morph_type && <Row label={t("info.morph")} value={s.morph_type} source={src} />}
            <Row
              label={t("info.distance")}
              value={
                info.distance
                  ? t("info.distanceValue", { pc: fmt(info.distance.pc, 1), ly: fmt(info.distance.ly, 1) })
                  : unknown
              }
              source={info.distance ? info.distance.source : undefined}
            />
            <Row
              label={t("info.pm")}
              value={
                s?.pmra_mas_yr != null
                  ? t("info.pmValue", { ra: fmt(s.pmra_mas_yr, 1), dec: fmt(s.pmdec_mas_yr, 1) })
                  : unknown
              }
              source={src}
            />
            {s?.radvel_km_s != null && (
              <Row label={t("info.radvel")} value={`${fmt(s.radvel_km_s, 1)} km/s`} source={src} />
            )}
            {s?.mags && Object.keys(s.mags).length > 0 && (
              <Row
                label={t("info.mags")}
                value={Object.entries(s.mags)
                  .map(([k, v]) => `${k} ${fmt(v, 2)}`)
                  .join(" · ")}
                source={src}
              />
            )}
            {s?.ra != null && s.dec != null && (
              <Row label={t("info.coords")} value={raDecText(s.ra, s.dec)} source={src} />
            )}
          </dl>
          {info.wikipedia && (
            <div className="mt-4 rounded-xl border border-white/10 bg-space-950/50 p-3 text-sm">
              <p className="text-ink-300">{info.wikipedia.extract}</p>
              <a
                href={info.wikipedia.url}
                target="_blank"
                rel="noreferrer noopener"
                className="mt-2 inline-flex items-center gap-1 text-nebula-300 hover:underline"
              >
                {t("info.wiki")} ({info.wikipedia.lang}){" "}
                <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            </div>
          )}
          <p className="mt-3 text-xs text-ink-400">
            {info.from_cache && `${t("info.fromCache")} · `}
            {info.fetched_at}
            {info.unavailable.length > 0 &&
              ` · ${t("info.unavailable", { list: info.unavailable.join(", ") })}`}
          </p>
        </>
      )}
    </aside>
  );
}
