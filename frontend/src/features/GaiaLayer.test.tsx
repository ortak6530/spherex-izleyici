import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import CutoutView from "../components/CutoutView";
import ResultPanel from "./ResultPanel";
import type { GaiaLayer, TimeCompareResult } from "./compareTypes";

afterEach(cleanup);

const epoch = (date: string) => ({
  image_id: `dr1:${date}:D5`,
  release: "dr1",
  calib_family: "R7",
  obs_id: date,
  detector: 5,
  date_obs: `${date}T00:00:00Z`,
  wavelength_um: 4.1,
  bandwidth_um: 0.03,
  pipeline_version: "7.0.5",
  fits_url: "https://irsa.ipac.caltech.edu/x.fits",
  zodi_median: 0.1,
  bad_fraction: 0.01,
  target_px: [29.5, 29.5] as [number, number],
  pixel_scale_arcsec: 6.15,
});

function result(gaia: GaiaLayer | { unavailable: true; source: string }): TimeCompareResult {
  return {
    id: "c1",
    kind: "time",
    target: { ra: 269.45, dec: 4.74 },
    size_deg: 0.1,
    zodi: "sub",
    a: epoch("2025-08-25"),
    b: epoch("2026-09-22"),
    channel: { delta_um: 0.005, bandwidth_um: 0.03, ratio: 0.14, status: "match" },
    warnings: [],
    orientation: { north_deg: 90, east_deg: 180, pixel_scale_arcsec: 6.15 },
    width: 59,
    height: 59,
    a_b64: "",
    b_b64: "",
    diff_b64: "",
    sigma_b64: "",
    shared_limits: [0, 1],
    diff_limit: 1,
    background: { a: 0.1, b: 0.1 },
    normalization: { enabled: true, factor: 0.98 },
    shift: { arcsec: 12.5, px: 2.03, pa_deg: 347 },
    expected_shift: null,
    photometry: { a: null, b: null, change: null, change_normalized: null },
    difference: { n: 0 },
    dt_days: 393,
    gaia,
  };
}

const LAYER: GaiaLayer = {
  markers: [{ source_id: "1", px: [29.6, 29.2], g_mag: 8.2, has_pm: true }],
  n_field: 422,
  g_limit: 19,
  radius_deg: 0.0707,
  truncated: false,
  target: {
    source_id: "4472832130942575872",
    g_mag: 8.19,
    separation_2016_arcsec: 0.003,
    match_radius_arcsec: 6.15,
    chance_probability: 0.00001,
    chance_probability_radius: 0.218,
    parallax_mas: 546.98,
    pmra_mas_yr: -801.6,
    pmdec_mas_yr: 10362.4,
    ruwe: 1.08,
    has_pm: true,
    has_parallax: true,
    expected_a_px: [29.1, 29.6],
    expected_b_px: [28.9, 27.8],
    expected_shift_arcsec: 11.07,
    difference_px: 0.23,
    separation_a_arcsec: 2.39,
  },
  nearest_separation_arcsec: 0.003,
  chance_probability: 0.218,
  source: "ESA Gaia DR3 (gaiadr3.gaia_source)",
  epoch: "J2016.0 → SPHEREx tarihleri (öz hareket + yıllık paralaks)",
  note: "Gaia işaretleri olası karşılıklardır (aday); kesin eşleşme değildir.",
};

describe("Gaia layer", () => {
  it("presents the counterpart as a candidate with its chance probability and parallax-corrected shift", () => {
    render(<ResultPanel r={result(LAYER)} />);
    expect(screen.getByText(/Olası karşılık \(aday\): Gaia DR3 4472832130942575872/)).toBeTruthy();
    expect(screen.getByText(/< %0,1 \(6\.15″ eşleştirme yarıçapının tamamında %21\.8\)/)).toBeTruthy();
    expect(screen.getByText(/beklenen kayma 11\.07″; ölçülen 12\.50″, fark 0\.23 piksel/)).toBeTruthy();
    expect(screen.getByText(/kesin eşleşme değildir/)).toBeTruthy();
    // the one-sentence explanation shows the density and radii the number comes from
    const how = screen.getByText(/Olasılık nasıl hesaplandı/).textContent!;
    expect(how).toMatch(/255″ yarıçaplı dairede G < 19 olan 422 Gaia kaynağı/);
    expect(how).toMatch(/ρ = 7\.4\d kaynak\/yay dakikası²/);
    expect(how).toMatch(/P = 1 − exp\(−π·r²·ρ\)/);
  });

  it("says 'veri yok' when Gaia has no motion, never 'yeni keşif' when nothing matches", () => {
    const noPm = {
      ...LAYER,
      target: {
        ...LAYER.target!,
        has_pm: false,
        expected_a_px: null,
        expected_b_px: null,
        expected_shift_arcsec: null,
      },
    };
    const { unmount } = render(<ResultPanel r={result(noPm)} />);
    expect(screen.getByText(/beklenen konum hesaplanmadı \(veri yok\)/)).toBeTruthy();
    unmount();
    render(<ResultPanel r={result({ ...LAYER, target: null, nearest_separation_arcsec: 9.4 })} />);
    expect(screen.getByText(/en yakını 9\.4″\). Bu bir "yeni keşif" anlamına gelmez/)).toBeTruthy();
  });

  it("draws candidate rings and the expected A/B diamonds on the image", () => {
    const { container } = render(
      <CutoutView
        cutout={{
          raw: {
            width: 59,
            height: 59,
            meta: {
              unit: "MJy/sr",
              target_px: [29.5, 29.5],
              wavelength_um: 4.1,
              date_obs: "2025-08-25T00:00:00Z",
              north_deg: 90,
              east_deg: 180,
              pixel_scale_arcsec: 6.15,
            },
          },
          data: new Float32Array(59 * 59),
          lambda: null,
        }}
        limits={[0, 1]}
        stretch="linear"
        cmap="inferno"
        gaia={{
          markers: LAYER.markers,
          expected: [
            { label: "Gaia A", px: [29.1, 29.6] },
            { label: "Gaia B", px: [28.9, 27.8] },
          ],
        }}
      />,
    );
    const layer = container.querySelector("g[data-layer='gaia']")!;
    expect(layer.querySelectorAll("circle")).toHaveLength(1);
    expect(layer.querySelectorAll("path")).toHaveLength(2);
    expect([...layer.querySelectorAll("text")].map((n) => n.textContent)).toEqual(["Gaia A", "Gaia B"]);
  });

  it("keeps working when Gaia is unreachable", () => {
    render(<ResultPanel r={result({ unavailable: true, source: "ESA Gaia DR3" })} />);
    expect(screen.getByText(/Gaia DR3 şu an erişilemedi/)).toBeTruthy();
  });
});
