// Thin fetch wrapper. The backend error contract is {"code": "..."}; UI text comes from i18n.

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public body: Record<string, unknown> = {}, // extra fields, e.g. attempts_left, retry_after_s
  ) {
    super(code);
  }
}

async function fail(res: Response): Promise<never> {
  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  throw new ApiError(res.status, (body.code as string | undefined) ?? `HTTP_${res.status}`, body);
}

async function send<T>(method: "POST" | "DELETE", path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) return fail(res);
  return (await res.json()) as T;
}

export const apiDelete = <T>(path: string) => send<T>("DELETE", path);

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`/api/v1${path}`, { credentials: "same-origin", signal });
  if (!res.ok) return fail(res);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return send<T>("POST", path, body ?? {});
}

export interface Target {
  kind: "object" | "coordinate" | "solar_system";
  key: string;
  name: string;
  main_id?: string | null;
  query: string;
  ra?: number;
  dec?: number;
  otype?: string | null;
  source: string;
  ra_j2000?: number;
  dec_j2000?: number;
  pmra_mas_yr?: number | null;
  pmdec_mas_yr?: number | null;
  epoch?: number;
  moved_since_j2000_arcsec?: number;
  input_format?: string;
  designation?: string;
  body_kind?: string;
  orbit_class?: string;
}

export interface Candidate {
  label: string;
  main_id?: string | null;
  otype?: string;
  description?: string;
  source: string;
  solar_system?: boolean;
}

export interface Suggestion {
  kind: "name" | "coordinate";
  label: string;
  query: string; // what /resolve receives when the suggestion is picked
  detail?: string | null;
  source: "local" | "Sesame" | "SIMBAD" | "JPL" | "input";
  main_id?: string;
  solar_system?: boolean;
  ra?: number;
  dec?: number;
}

export interface SuggestResponse {
  items: Suggestion[];
  unavailable: string[];
  partial?: boolean;
}

export interface ResolveResponse {
  kind: "object" | "coordinate" | "solar_system" | "ambiguous" | "not_found";
  target?: Target;
  alternatives?: Target[];
  candidates?: Candidate[];
  upstream_unavailable?: string[];
}

export interface ObservationImage {
  image_id: string;
  release: string;
  obs_id: string;
  detector: number;
  date_obs: string;
  mjd: number;
  fits_url: string;
  wavelength_um: number | null;
  bandwidth_um: number | null;
  channel: number | null;
  on_detector: boolean | null;
  x: number | null;
  y: number | null;
  pipeline_version: string | null;
  error?: string | null;
}

export interface Visit {
  index: number;
  label: string;
  start: string;
  end: string;
  releases: string[];
  images_per_detector: Record<string, number>;
  images: ObservationImage[];
}

export interface ObservationsResult {
  ra: number;
  dec: number;
  detector: number;
  visits: Visit[];
  total_images?: number;
  no_coverage: boolean;
  releases: Record<string, { label: string; calib_family: string; show_with_warning: boolean }>;
}

export interface CutoutMeta {
  unit: string;
  zodi: "sub" | "raw";
  zodi_model: string | null;
  zodi_median: number;
  target_px: [number, number];
  wavelength_um: number;
  bandwidth_um: number;
  wavelength_min_um: number;
  wavelength_max_um: number;
  wavelength_gradient_deg: number;
  date_obs: string;
  mjd_avg: number;
  detector: number;
  obs_id: string;
  pipeline_version: string | null;
  psf_fwhm_arcsec: number | null;
  sps_epa: number | null;
  bad_fraction: number;
  flag_fractions: Record<string, number>;
  north_deg: number;
  east_deg: number;
  pixel_scale_arcsec: number;
  center_ra: number;
  center_dec: number;
}

export interface CutoutResult {
  image_id: string;
  release: string;
  fits_url: string;
  size_deg: number;
  width: number;
  height: number;
  data_b64: string;
  lambda_b64: string;
  stats: { p01: number | null; p50: number | null; p995: number | null };
  meta: CutoutMeta;
}

export interface MovingFrame {
  image_id: string;
  release: string;
  obs_id: string;
  detector: number;
  mjd: number;
  mjd_end: number;
  date_obs: string;
  ra: number; // predicted position of the object in this frame (JPL Horizons via MOST)
  dec: number;
  sun_dist_au: number | null;
  geo_dist_au: number | null;
  phase_deg: number | null;
  vmag: number | null;
  dist_ctr_deg: number | null;
  fits_url: string;
}

export interface MovingVisit {
  index: number;
  label: string;
  start: string;
  end: string;
  releases: string[];
  frames_per_detector: Record<string, number>;
  frame_ids: string[];
}

export interface MovingResult {
  designation: string;
  horizons_name: string | null;
  start: string;
  end: string;
  frames: MovingFrame[];
  visits: MovingVisit[];
  skipped_releases: Record<string, number>;
  track: Array<{
    mjd: number;
    date: string;
    ra: number;
    dec: number;
    sun_dist_au: number | null;
    geo_dist_au: number | null;
    vmag: number | null;
  }>;
  source: string;
}

export interface JobState<T> {
  id: string;
  kind: string;
  status: "running" | "done" | "error";
  steps: Array<{ step: string; [k: string]: unknown }>;
  result: T | null;
  error: { code: string; upstream?: string } | null;
}

export interface ObjectInfo {
  main_id: string;
  simbad: {
    main_id: string;
    otype: string | null;
    otype_label?: string | null;
    otype_desc?: string | null;
    ra: number | null;
    dec: number | null;
    sp_type: string | null;
    morph_type: string | null;
    plx_mas: number | null;
    plx_err_mas?: number | null;
    pmra_mas_yr: number | null;
    pmdec_mas_yr: number | null;
    redshift: number | null;
    radvel_km_s: number | null;
    major_axis_arcmin?: number | null;
    mags?: Record<string, number | null>;
  } | null;
  distance: { pc: number; ly: number; method: string; source: string } | null;
  wikipedia: { lang: string; title: string; extract: string; url: string; wikidata: string } | null;
  sources: Record<string, string>;
  unavailable: string[];
  fetched_at: string;
  from_cache: boolean;
}

export interface ReleaseInfo {
  id: string;
  label: string;
  status: "active" | "staged" | "superseded" | "retired";
  calib_family: string;
  doi: string | null;
  show_with_warning: boolean;
  announced: boolean;
  notice: string | null;
  notes: string;
}

export interface ReleasesResponse {
  default: string;
  releases: ReleaseInfo[];
  last_update: string | null;
}

export interface Attribution {
  key: string;
  title: string;
  group?: "data" | "software";
  status?: "used" | "planned";
  purpose?: string;
  text?: string; // acknowledgement, verbatim from text_source
  text_source?: string;
  verified?: string;
  license?: string;
  note?: string;
  url?: string;
  dois?: string[];
  citations?: Array<{ label: string; url: string }>;
  references?: Array<{ label: string; url: string }>;
}
