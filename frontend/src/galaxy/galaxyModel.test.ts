import { describe, expect, it } from "vitest";

import { GALAXY, detectQuality, generateGalaxy, omegaAt, particleBudget } from "./galaxyModel";

describe("galaxy model", () => {
  it("is deterministic for a given seed", () => {
    const a = generateGalaxy(500, 1);
    const b = generateGalaxy(500, 1);
    expect(Array.from(a.radius)).toEqual(Array.from(b.radius));
  });

  it("keeps every particle inside the disk and has a bulge", () => {
    const g = generateGalaxy(5000);
    expect(Math.max(...g.radius)).toBeLessThanOrEqual(GALAXY.rMax);
    const bulge = g.kind.reduce((n, k) => n + k, 0) / g.count;
    expect(bulge).toBeGreaterThan(0.1);
    expect(bulge).toBeLessThan(0.2);
  });

  it("rotates differentially: inner regions faster than outer", () => {
    expect(omegaAt(0.2)).toBeGreaterThan(omegaAt(1.0));
    expect(omegaAt(1.0)).toBeGreaterThan(omegaAt(1.6));
    // "very slow": the outer disk needs more than 10 minutes per turn
    expect((2 * Math.PI) / omegaAt(1.5) / 60).toBeGreaterThan(10);
  });

  it("reduces particles on weak devices", () => {
    expect(detectQuality({ hardwareConcurrency: 2, coarsePointer: true })).toBe("low");
    expect(detectQuality({ hardwareConcurrency: 8, deviceMemory: 8, coarsePointer: true })).toBe("medium");
    expect(detectQuality({ hardwareConcurrency: 12, deviceMemory: 16, coarsePointer: false })).toBe("high");
    expect(particleBudget("low")).toBeLessThan(particleBudget("high"));
  });
});
