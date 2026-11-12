// Pure, deterministic particle model for the background galaxy (artistic, not to scale).
//
// Physics-flavoured choices:
//  - Exponential stellar disk + Gaussian bulge.
//  - Spiral arms are a *density-wave pattern*: a logarithmic spiral r = r0 * exp(b * theta) that
//    rotates rigidly at pattern speed OMEGA_P, while every star orbits with a differential angular
//    speed omega(r) = OMEGA0 / (r + R_SOFT) (roughly a flat rotation curve: inner stars are faster).
//    Stars brighten while they pass through an arm. This keeps the arms from winding up over time.
//  The shader (GalaxyBackground.tsx) uses the same constants.

export const GALAXY = {
  arms: 4,
  pitchDeg: 13,
  r0: 0.08,
  rMax: 1.7,
  scaleLength: 0.42,
  bulgeSigma: 0.13,
  bulgeFraction: 0.14,
  omega0: 0.012, // rad/s at r = 1 - R_SOFT (very slow)
  rSoft: 0.15,
  omegaP: 0.0095, // pattern speed, rad/s (one turn ~ 11 min)
} as const;

export const armPitchB = Math.tan((GALAXY.pitchDeg * Math.PI) / 180);

/** Differential angular speed (rad/s) at radius r, identical to the shader. */
export function omegaAt(r: number): number {
  return GALAXY.omega0 / (r + GALAXY.rSoft);
}

/** Small seeded PRNG (mulberry32) so every visitor sees the same galaxy. */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gauss(rand: () => number) {
  // Box-Muller
  const u = Math.max(rand(), 1e-12);
  const v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export interface GalaxyParticles {
  count: number;
  radius: Float32Array; // r
  angle: Float32Array; // initial azimuth (rad)
  height: Float32Array; // y offset above the disk plane
  size: Float32Array; // relative point size
  kind: Float32Array; // 0 = disk star (arm-modulated), 1 = bulge star
  color: Float32Array; // rgb triplets
}

export function generateGalaxy(count: number, seed = 20251215): GalaxyParticles {
  const rand = mulberry32(seed);
  const p: GalaxyParticles = {
    count,
    radius: new Float32Array(count),
    angle: new Float32Array(count),
    height: new Float32Array(count),
    size: new Float32Array(count),
    kind: new Float32Array(count),
    color: new Float32Array(count * 3),
  };
  const { rMax, scaleLength: h, bulgeSigma, bulgeFraction } = GALAXY;
  const tailNorm = 1 - Math.exp(-rMax / h);

  for (let i = 0; i < count; i++) {
    let r: number;
    let y: number;
    let rgb: [number, number, number];
    let size: number;
    let kind: number;

    if (rand() < bulgeFraction) {
      // Bulge: flattened Gaussian, warm old stars
      const x = gauss(rand) * bulgeSigma;
      const z = gauss(rand) * bulgeSigma;
      r = Math.min(Math.hypot(x, z), rMax);
      y = gauss(rand) * bulgeSigma * 0.55;
      const w = 0.85 + rand() * 0.15;
      rgb = [1.0 * w, 0.82 * w, 0.58 * w];
      size = 0.9 + rand() * 1.1;
      kind = 1;
    } else {
      // Disk: exponential surface density, truncated at rMax (inverse-CDF sampling)
      r = -h * Math.log(1 - rand() * tailNorm);
      r = Math.max(r, 0.03);
      y = gauss(rand) * (0.012 + 0.018 * r);
      const roll = rand();
      if (roll < 0.035) {
        rgb = [1.0, 0.42, 0.62]; // HII regions (pink)
        size = 2.2 + rand() * 1.6;
      } else if (roll < 0.25) {
        rgb = [0.62, 0.76, 1.0]; // young blue stars
        size = 1.2 + rand() * 1.4;
      } else {
        const w = 0.75 + rand() * 0.25;
        rgb = [0.86 * w, 0.88 * w, 0.95 * w]; // average disk stars
        size = 0.7 + rand() * 1.0;
      }
      kind = 0;
    }
    p.radius[i] = r;
    p.angle[i] = rand() * Math.PI * 2;
    p.height[i] = y;
    p.size[i] = size;
    p.kind[i] = kind;
    p.color.set(rgb, i * 3);
  }
  return p;
}

export type Quality = "high" | "medium" | "low";

/** Particle budget from device hints; refined at runtime by an FPS probe. */
export function particleBudget(q: Quality): number {
  return q === "high" ? 70_000 : q === "medium" ? 32_000 : 14_000;
}

export function detectQuality(nav: {
  hardwareConcurrency?: number;
  deviceMemory?: number;
  coarsePointer: boolean;
}): Quality {
  const cores = nav.hardwareConcurrency ?? 4;
  const mem = nav.deviceMemory ?? 4;
  if (cores <= 2 || mem <= 2) return "low";
  if (nav.coarsePointer || cores <= 4 || mem <= 4) return "medium";
  return "high";
}
