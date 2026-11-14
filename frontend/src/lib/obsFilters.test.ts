import { describe, expect, it } from "vitest";

import { isActive, NO_FILTERS, passes, toExport } from "./obsFilters";

const img = (date: string, release: string, lam: number | null) => ({
  date_obs: `${date}T03:00:00Z`,
  release,
  wavelength_um: lam,
});

describe("observation filters", () => {
  it("same rules as the server: date range, release, λ (unknown λ fails a λ filter)", () => {
    const f = { from: "2025-09-01", to: "2026-06-30", releases: ["qr3"], lamMin: "1,0", lamMax: "2.0" };
    expect(passes(f, img("2026-01-02", "qr3", 1.5))).toBe(true);
    expect(passes(f, img("2025-08-30", "qr3", 1.5))).toBe(false);
    expect(passes(f, img("2026-07-01", "qr3", 1.5))).toBe(false);
    expect(passes(f, img("2026-01-02", "dr1", 1.5))).toBe(false);
    expect(passes(f, img("2026-01-02", "qr3", null))).toBe(false);
    expect(passes(f, img("2026-01-02", "qr3", 2.5))).toBe(false);
    expect(passes(NO_FILTERS, img("2020-01-01", "x", null))).toBe(true);
  });

  it("is sent to the Excel export in the server's field names", () => {
    expect(isActive(NO_FILTERS)).toBe(false);
    expect(toExport(NO_FILTERS)).toEqual({});
    expect(toExport({ from: "2025-09-01", to: "", releases: ["dr1"], lamMin: "0,9", lamMax: "x" })).toEqual({
      date_from: "2025-09-01",
      releases: ["dr1"],
      lam_min_um: 0.9,
    });
  });
});
