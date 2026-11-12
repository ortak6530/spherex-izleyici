// Client-side rendering of SPHEREx cutouts: stretch + colormap into an ImageData (instant re-render).
import { COLORMAP_HEX } from "./colormapData";

export type Stretch = "linear" | "asinh" | "log";
export type Colormap = "viridis" | "magma" | "inferno" | "cividis" | "gray";
export const COLORMAPS: Colormap[] = ["viridis", "magma", "inferno", "cividis", "gray"];
export const STRETCHES: Stretch[] = ["asinh", "linear", "log"];

const LUT_CACHE = new Map<string, Uint8ClampedArray>();

/** 256-entry RGB lookup table built from 64 matplotlib samples. */
export function lut(name: Colormap): Uint8ClampedArray {
  const hit = LUT_CACHE.get(name);
  if (hit) return hit;
  const hex = COLORMAP_HEX[name];
  const n = hex.length / 6;
  const stops = Array.from({ length: n }, (_, i) =>
    [0, 2, 4].map((o) => parseInt(hex.substr(i * 6 + o, 2), 16)),
  );
  const out = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const f = (i / 255) * (n - 1);
    const a = Math.floor(f);
    const b = Math.min(a + 1, n - 1);
    const t = f - a;
    for (let c = 0; c < 3; c++) out[i * 3 + c] = stops[a][c] * (1 - t) + stops[b][c] * t;
  }
  LUT_CACHE.set(name, out);
  return out;
}

export function stretchValue(v: number, s: Stretch): number {
  // v already normalised to [0, 1]
  if (s === "linear") return v;
  if (s === "asinh") return Math.asinh(v * 10) / Math.asinh(10);
  return Math.log10(1 + 1000 * v) / 3; // log10(1001) ~ 3
}

export function decodeFloat32(b64: string): Float32Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Float32Array(bytes.buffer);
}

/** Robust display limits from percentiles of the finite pixels (optionally over several images). */
export function percentileLimits(arrays: Float32Array[], lo = 0.5, hi = 99.5): [number, number] {
  const vals: number[] = [];
  for (const a of arrays) for (const v of a) if (Number.isFinite(v)) vals.push(v);
  if (!vals.length) return [0, 1];
  vals.sort((x, y) => x - y);
  const q = (p: number) =>
    vals[Math.min(vals.length - 1, Math.max(0, Math.round((p / 100) * (vals.length - 1))))];
  const a = q(lo);
  const b = q(hi);
  return b > a ? [a, b] : [a, a + 1e-6];
}

/** Render into RGBA. FITS row 0 is the bottom row, so rows are flipped for the screen. */
export function renderImage(
  data: Float32Array,
  width: number,
  height: number,
  limits: [number, number],
  stretch: Stretch,
  cmap: Colormap | "diverging",
): ImageData {
  const img = new ImageData(width, height);
  const px = img.data;
  const [lo, hi] = limits;
  const span = hi - lo || 1;
  const table = cmap === "diverging" ? null : lut(cmap);
  for (let y = 0; y < height; y++) {
    const srcRow = (height - 1 - y) * width;
    for (let x = 0; x < width; x++) {
      const v = data[srcRow + x];
      const o = (y * width + x) * 4;
      if (!Number.isFinite(v)) {
        // masked / bad pixel: neutral dark grey so it is not mistaken for sky
        px[o] = 40;
        px[o + 1] = 42;
        px[o + 2] = 52;
        px[o + 3] = 255;
        continue;
      }
      if (table) {
        const t = stretchValue(Math.min(1, Math.max(0, (v - lo) / span)), stretch);
        const k = Math.round(t * 255) * 3;
        px[o] = table[k];
        px[o + 1] = table[k + 1];
        px[o + 2] = table[k + 2];
      } else {
        // symmetric diverging map for difference images: blue (negative) - white - red (positive)
        const m = Math.max(Math.abs(lo), Math.abs(hi)) || 1;
        const t = Math.max(-1, Math.min(1, v / m));
        const w = 1 - Math.abs(t);
        px[o] = t > 0 ? 255 : Math.round(255 * w + 60 * (1 - w));
        px[o + 1] = Math.round(255 * w + 70 * (1 - w));
        px[o + 2] = t < 0 ? 255 : Math.round(255 * w + 60 * (1 - w));
      }
      px[o + 3] = 255;
    }
  }
  return img;
}
