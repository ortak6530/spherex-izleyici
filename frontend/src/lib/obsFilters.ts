// Observation filters (date range, data release, wavelength range). Applied to the visit / exposure
// lists on the page and sent unchanged to the Excel export (backend ExportFilters).
export type ObsFilters = {
  from: string; // YYYY-MM-DD or ""
  to: string;
  releases: string[]; // empty = all active releases
  lamMin: string; // µm as typed, "" = no limit
  lamMax: string;
};

export const NO_FILTERS: ObsFilters = { from: "", to: "", releases: [], lamMin: "", lamMax: "" };

const num = (s: string) => {
  const v = Number(s.replace(",", "."));
  return s.trim() === "" || !Number.isFinite(v) ? null : v;
};

export function isActive(f: ObsFilters) {
  return !!(f.from || f.to || f.releases.length || num(f.lamMin) !== null || num(f.lamMax) !== null);
}

/** Same rule as the server (api/v1/export.py ExportFilters.keep): an unknown λ fails a λ filter. */
export function passes(
  f: ObsFilters,
  img: { date_obs: string; release: string; wavelength_um: number | null },
): boolean {
  const day = img.date_obs.slice(0, 10);
  if (f.from && day < f.from) return false;
  if (f.to && day > f.to) return false;
  if (f.releases.length && !f.releases.includes(img.release)) return false;
  const lo = num(f.lamMin);
  const hi = num(f.lamMax);
  if (lo !== null || hi !== null) {
    if (img.wavelength_um === null) return false;
    if (lo !== null && img.wavelength_um < lo) return false;
    if (hi !== null && img.wavelength_um > hi) return false;
  }
  return true;
}

export function toExport(f: ObsFilters) {
  const out: Record<string, unknown> = {};
  if (f.from) out.date_from = f.from;
  if (f.to) out.date_to = f.to;
  if (f.releases.length) out.releases = f.releases;
  const lo = num(f.lamMin);
  const hi = num(f.lamMax);
  if (lo !== null) out.lam_min_um = lo;
  if (hi !== null) out.lam_max_um = hi;
  return out;
}
