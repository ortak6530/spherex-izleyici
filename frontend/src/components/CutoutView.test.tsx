import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import CutoutView, { type DecodedCutout, type MotionTrack } from "./CutoutView";

afterEach(cleanup);

const cutout: DecodedCutout = {
  raw: {
    width: 60,
    height: 60,
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
  data: new Float32Array(3600),
  lambda: null,
};
const TRACK: MotionTrack = {
  expected: [
    { label: "2010.0", mjd: 55197, px: [29.5, 2.5] },
    { label: "2016.0", mjd: 57388, px: [29.6, 12.6] },
    { label: "A", mjd: 60912, px: [29.5, 28.5] },
    { label: "B", mjd: 61305, px: [29.4, 30.3] },
  ],
  measured: [
    { label: "A", px: [29.6, 28.9] },
    { label: "B", px: [29.3, 30.8] },
  ],
  source: "SIMBAD J2000 + öz hareket (paralaks ihmal)",
  note: "Çizgi, bilinen hareketten hesaplanan beklenen konumdur; ölçüm değildir.",
};

describe("motion track layer", () => {
  it("draws the expected path with its epochs and the measured centroids, flipped to screen y", () => {
    const { container } = render(
      <CutoutView cutout={cutout} limits={[0, 1]} stretch="linear" cmap="inferno" track={TRACK} />,
    );
    const line = container.querySelector("polyline")!;
    // FITS y (up) -> screen y (down): 2010.0 at y=2.5 is near the bottom (60 - 3 = 57)
    expect(line.getAttribute("points")!.split(" ")[0]).toBe("30,57");
    const labels = [...container.querySelectorAll("svg text")].map((n) => n.textContent);
    expect(labels).toEqual(expect.arrayContaining(["2010.0", "2016.0", "A", "B"]));
    expect(container.querySelectorAll("g[transform] line")).toHaveLength(4); // two × marks
  });

  it("has no track layer when none is given (e.g. no proper motion)", () => {
    const { container } = render(
      <CutoutView cutout={cutout} limits={[0, 1]} stretch="linear" cmap="inferno" />,
    );
    expect(container.querySelector("polyline")).toBeNull();
  });
});
