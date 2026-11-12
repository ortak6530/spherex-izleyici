import { describe, expect, it } from "vitest";

import { lut, percentileLimits, stretchValue } from "./image";

describe("rendering helpers", () => {
  it("builds 256-entry colormap tables", () => {
    const t = lut("viridis");
    expect(t.length).toBe(768);
    // viridis starts dark purple and ends yellow
    expect(t[0]).toBeLessThan(80);
    expect(t[765]).toBeGreaterThan(200);
  });

  it("stretches stay within [0,1] and are monotonic", () => {
    for (const s of ["linear", "asinh", "log"] as const) {
      expect(stretchValue(0, s)).toBeCloseTo(0);
      expect(stretchValue(1, s)).toBeCloseTo(1, 2);
      expect(stretchValue(0.6, s)).toBeGreaterThan(stretchValue(0.3, s));
    }
  });

  it("ignores NaN pixels when computing limits", () => {
    const a = new Float32Array([NaN, 1, 2, 3, 4, 5, NaN, 100]);
    const [lo, hi] = percentileLimits([a], 0, 100);
    expect(lo).toBe(1);
    expect(hi).toBe(100);
  });
});
