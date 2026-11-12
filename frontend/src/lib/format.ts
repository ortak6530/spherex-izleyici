import type { TFunction } from "i18next";

import { ApiError } from "./api";

export const fmt = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined || !Number.isFinite(v) ? "—" : v.toFixed(digits);

export function raDecText(ra: number, dec: number) {
  const h = ra / 15;
  const hh = Math.floor(h);
  const mm = Math.floor((h - hh) * 60);
  const ss = ((h - hh) * 60 - mm) * 60;
  const sign = dec < 0 ? "−" : "+";
  const d = Math.abs(dec);
  const dd = Math.floor(d);
  const dm = Math.floor((d - dd) * 60);
  const ds = ((d - dd) * 60 - dm) * 60;
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${p(hh)}h${p(mm)}m${ss.toFixed(1).padStart(4, "0")}s ${sign}${p(dd)}°${p(dm)}′${ds.toFixed(0).padStart(2, "0")}″`;
}

export function errorText(t: TFunction, e: unknown): string {
  const code = e instanceof ApiError ? e.code : "generic";
  return t(`errors.${code}`, { defaultValue: t("errors.generic") });
}

export type Warning = { code: string; [k: string]: unknown };

/** Turkish sentence for a server warning code, filled only with values the server computed. */
export function warningText(t: TFunction, w: Warning): string {
  const p: Record<string, unknown> = { ...w };
  if (typeof w.delta_um === "number") p.dl = (Math.abs(w.delta_um) * 1000).toFixed(1);
  if (typeof w.ratio === "number") p.ratio = w.ratio.toFixed(2);
  if (typeof w.fraction === "number") p.pct = (w.fraction * 100).toFixed(0);
  if (typeof w.snr === "number") p.snr = w.snr.toFixed(1);
  if (Array.isArray(w.lines)) p.lines = w.lines.join(", ");
  if (w.epoch) p.epoch = String(w.epoch).toUpperCase();
  if (w.code === "CROSS_RELEASE") {
    p.a = String(w.a).toUpperCase();
    p.b = String(w.b).toUpperCase();
    p.fix = t(w.flux_corrected ? "warnings.CROSS_RELEASE_FIXED" : "warnings.CROSS_RELEASE_NOFIX");
  }
  return t(`warnings.${w.code}`, { ...p, defaultValue: w.code });
}
