import { Compass, Radio } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiGet, apiPost, type Target } from "../lib/api";
import { errorText, fmt, raDecText } from "../lib/format";
import { runJob } from "../lib/jobs";

type City = { name: string; lat: number; lon: number; wikidata: string };
type Event = { utc: string; az_deg?: number; alt_deg?: number } | null;
type Sky = {
  alt_deg: number;
  az_deg: number;
  rise: Event;
  set: Event;
  transit: Event;
  always_up: boolean;
  never_up: boolean;
  horizon: string;
};
export type LivePosition = {
  utc: string;
  ra: number;
  dec: number;
  method: string;
  moved_since_j2000_arcsec?: number | null;
  mag?: number | null;
  delta_au?: number | null;
  site: { name: string | null; lat: number; lon: number; source: string } | null;
  sky?: Sky;
  stale?: string;
};
type Step = { step: string; position?: LivePosition };

const DIRS = ["K", "KD", "D", "GD", "G", "GB", "B", "KB"];
const direction = (az: number) => DIRS[Math.round((((az % 360) + 360) % 360) / 45) % 8];

function time(iso: string, tz: string, lang: string) {
  return new Date(iso).toLocaleString(lang === "tr" ? "tr-TR" : "en-GB", {
    timeZone: tz,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "Şu an nerede?" + "Benim gökyüzümde": refreshed every 10 s by a server job (WS, HTTP fallback). */
export default function LivePanel({ target }: { target: Target }) {
  const { t, i18n } = useTranslation();
  const id = useId();
  const [cities, setCities] = useState<City[]>([]);
  const [city, setCity] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [custom, setCustom] = useState<{ lat: number; lon: number } | null>(null);
  const [pos, setPos] = useState<LivePosition | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ cities: City[] }>("/live/cities")
      .then((r) => setCities(r.cities))
      .catch(() => setCities([]));
  }, []);

  // One server job at a time; when it ends (10 min) the next one starts while the panel is open
  useEffect(() => {
    const ctrl = new AbortController();
    const body: Record<string, unknown> = { q: target.query };
    if (city && city !== "custom") body.city = city;
    if (city === "custom" && custom) Object.assign(body, custom);
    let stop = false;
    const loop = async () => {
      while (!stop) {
        try {
          const r = await runJob<{ position: LivePosition | null }>(
            () => apiPost("/live/start", body),
            (s) => {
              const step = s as Step;
              if (step.step === "position" && step.position) {
                setPos(step.position);
                setError(null); // a fresh position clears an earlier error
              }
            },
            ctrl.signal,
          );
          if (r.position) setPos(r.position);
        } catch (e) {
          if (!stop) setError(errorText(t, e));
          return;
        }
      }
    };
    void loop();
    return () => {
      stop = true;
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.key, city, custom]);

  const lang = i18n.language;
  const tz = pos?.site?.name ? "Europe/Istanbul" : "UTC";
  const tzLabel = tz === "UTC" ? "UTC" : t("live.trTime");
  const sel = "h-9 w-full rounded-lg border border-white/10 bg-space-950/70 px-2 text-sm text-ink-100";

  return (
    <section className="glass space-y-3 rounded-2xl p-5" aria-labelledby={`${id}-t`}>
      <h3 id={`${id}-t`} className="flex items-center gap-2 font-display text-lg font-semibold text-ink-100">
        <Radio className="size-5 text-nebula-300" aria-hidden="true" />
        {t("live.title")}
      </h3>
      {error && (
        <p className="text-sm text-danger-400" role="alert">
          {error}
        </p>
      )}
      {!pos && !error && <p className="text-sm text-ink-400">{t("live.loading")}</p>}
      {pos && (
        <div className="space-y-1 text-sm" aria-live="polite">
          <p className="font-mono text-ink-100">{raDecText(pos.ra, pos.dec)}</p>
          {pos.moved_since_j2000_arcsec ? (
            <p className="text-xs text-ink-300">
              {t("live.moved", { arcsec: fmt(pos.moved_since_j2000_arcsec, 1) })}
            </p>
          ) : null}
          {pos.mag !== undefined && pos.mag !== null && (
            <p className="text-xs text-ink-300">
              {t("live.mag", { mag: fmt(pos.mag, 1) })}
              {pos.delta_au ? ` · ${t("live.delta", { au: fmt(pos.delta_au, 3) })}` : ""}
            </p>
          )}
          <p className="text-xs text-ink-400">
            {t("live.updated", { at: new Date(pos.utc).toISOString().slice(11, 19) })} · {pos.method}
            {pos.stale ? ` · ${t("live.stale")}` : ""}
          </p>
        </div>
      )}

      <div className="space-y-2 border-t border-white/10 pt-3">
        <label className="block text-sm text-ink-300" htmlFor={`${id}-city`}>
          <span className="flex items-center gap-1.5">
            <Compass className="size-4" aria-hidden="true" />
            {t("live.mySky")}
          </span>
          <select
            id={`${id}-city`}
            className={`${sel} mt-1`}
            value={city}
            onChange={(e) => setCity(e.target.value)}
          >
            <option value="">{t("live.pickCity")}</option>
            {cities.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
            <option value="custom">{t("live.custom")}</option>
          </select>
        </label>
        {city === "custom" && (
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const la = Number(lat.replace(",", "."));
              const lo = Number(lon.replace(",", "."));
              if (Number.isFinite(la) && Number.isFinite(lo) && Math.abs(la) <= 90 && Math.abs(lo) <= 180)
                setCustom({ lat: la, lon: lo });
            }}
          >
            <label className="text-xs text-ink-400">
              {t("live.lat")}
              <input
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                inputMode="decimal"
                className={`${sel} w-24`}
              />
            </label>
            <label className="text-xs text-ink-400">
              {t("live.lon")}
              <input
                value={lon}
                onChange={(e) => setLon(e.target.value)}
                inputMode="decimal"
                className={`${sel} w-24`}
              />
            </label>
            <button
              type="submit"
              className="h-9 cursor-pointer rounded-lg bg-nebula-500 px-3 text-sm text-white hover:bg-nebula-600"
            >
              {t("live.apply")}
            </button>
          </form>
        )}
        {!city && <p className="text-xs text-ink-400">{t("live.noLocation")}</p>}
        {pos?.sky && (
          <div className="space-y-1 text-sm">
            <p className={pos.sky.alt_deg >= 0 ? "text-ok-400" : "text-ink-300"}>
              {pos.sky.alt_deg >= 0
                ? t("live.up", {
                    alt: fmt(pos.sky.alt_deg, 0),
                    az: fmt(pos.sky.az_deg, 0),
                    dir: direction(pos.sky.az_deg),
                  })
                : t("live.down", { alt: fmt(pos.sky.alt_deg, 0) })}
            </p>
            {pos.sky.always_up ? (
              <p className="text-xs text-ink-300">{t("live.alwaysUp")}</p>
            ) : pos.sky.never_up ? (
              <p className="text-xs text-ink-300">{t("live.neverUp")}</p>
            ) : (
              <ul className="text-xs text-ink-300">
                {pos.sky.rise && (
                  <li>
                    {t("live.rise")}: {time(pos.sky.rise.utc, tz, lang)} {tzLabel}
                    {pos.sky.rise.az_deg !== undefined ? ` (${direction(pos.sky.rise.az_deg)})` : ""}
                  </li>
                )}
                {pos.sky.transit && (
                  <li>
                    {t("live.transit")}: {time(pos.sky.transit.utc, tz, lang)} {tzLabel} ·{" "}
                    {fmt(pos.sky.transit.alt_deg ?? null, 0)}°
                  </li>
                )}
                {pos.sky.set && (
                  <li>
                    {t("live.set")}: {time(pos.sky.set.utc, tz, lang)} {tzLabel}
                    {pos.sky.set.az_deg !== undefined ? ` (${direction(pos.sky.set.az_deg)})` : ""}
                  </li>
                )}
              </ul>
            )}
            <p className="text-xs text-ink-400">
              {t("live.horizonNote")} {pos.site?.name ? t("live.citySource", { src: pos.site.source }) : ""}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
