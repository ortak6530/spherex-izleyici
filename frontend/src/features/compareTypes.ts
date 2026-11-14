import type { MotionTrack } from "../components/CutoutView";
import type { Warning } from "../lib/format";

export interface EpochMeta {
  image_id: string;
  release: string;
  calib_family: string;
  obs_id: string;
  detector: number;
  date_obs: string;
  wavelength_um: number;
  bandwidth_um: number;
  pipeline_version: string | null;
  fits_url: string;
  zodi_median: number;
  bad_fraction: number;
  target_px: [number, number];
  pixel_scale_arcsec: number;
}

export interface Photometry {
  flux_ujy: number;
  err_ujy: number;
  background_mjy_sr: number;
  aperture_px: number;
}

export interface TimeCompareResult {
  id: string;
  kind: "time";
  target: { ra: number; dec: number };
  size_deg: number;
  zodi: "sub" | "raw";
  a: EpochMeta;
  b: EpochMeta;
  channel: { delta_um: number; bandwidth_um: number; ratio: number; status: "match" | "warn" | "reject" };
  warnings: Warning[];
  orientation: { north_deg: number; east_deg: number; pixel_scale_arcsec: number };
  width: number;
  height: number;
  a_b64: string;
  b_b64: string;
  diff_b64: string;
  sigma_b64: string;
  shared_limits: [number, number];
  diff_limit: number;
  background: { a: number | null; b: number | null };
  normalization: { enabled: boolean; factor: number | null };
  flux_corrected_image?: string | null; // QR2 (R6) image multiplied by IRSA's QR3 correction
  track?: MotionTrack | null; // expected positions from proper motion (stars only)
  shift: { arcsec: number; px: number; pa_deg: number } | null;
  expected_shift: { arcsec: number; px: number; pm_mas_yr: number; source: string } | null;
  photometry: {
    a: Photometry | null;
    b: Photometry | null;
    change: { percent: number; err_percent: number; significance: number | null } | null;
    change_normalized: { percent: number; err_percent: number } | null;
  };
  difference: {
    n: number;
    mean?: number;
    std?: number;
    max_sigma?: number | null;
    max_radec?: [number, number];
  };
  dt_days: number;
  object_key?: string | null;
}
