import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import StatusBar from "../components/StatusBar";
import tr from "../i18n/tr.json";
import SpectrumPanel, { SpectrumChart, type SpectrumPoint } from "./SpectrumPanel";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const pt = (lam: number, flux: number, det: number): SpectrumPoint => ({
  image_id: `dr1:o${lam}:D${det}`,
  detector: det,
  release: "dr1",
  date_obs: "2025-05-30T00:00:00Z",
  wavelength_um: lam,
  bandwidth_um: 0.03,
  flux_ujy: flux,
  err_ujy: flux * 0.05,
  masked_in_aperture: 0,
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("spectrum", () => {
  it("draws one focusable point per measurement, on a log or linear axis", () => {
    const pts = [pt(0.9, 17386, 1), pt(1.74, 146196, 3), pt(4.57, 104831, 6)];
    const { rerender } = render(<SpectrumChart points={pts} log />);
    expect(screen.getAllByRole("img")).toHaveLength(1);
    expect(screen.getByLabelText(/λ 1\.740 µm · 146196 ± 7310 µJy · D3/)).toBeTruthy();
    expect(document.querySelectorAll("circle[tabindex='0']")).toHaveLength(3);
    rerender(<SpectrumChart points={pts} log={false} />);
    expect(document.querySelectorAll("circle[tabindex='0']")).toHaveLength(3);
  });

  it("runs the job for the selected visit and shows counts and method", async () => {
    const posted: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/sky/spectrum")) {
          posted.push(JSON.parse(init!.body as string));
          return json({ job_id: "sp1" });
        }
        return json({
          status: "done",
          steps: [],
          result: {
            visit: { index: 2, label: "2025-05", start: "2025-05-30", end: "2025-07-19" },
            points: [pt(1.74, 146196, 3)],
            counts: { exposures: 3, ok: 1, no_photometry: 1, off_detector: 1, error: 0 },
            method: "Basit açıklık fotometrisi …",
            unit: "µJy",
          },
        });
      }),
    );
    const target = {
      kind: "object",
      key: "luhman-16",
      name: "Luhman 16",
      query: "Luhman 16",
      source: "x",
      ra: 162.3,
      dec: -53.3,
    } as const;
    render(<SpectrumPanel target={target} visit={{ index: 2, label: "2025-05" }} />);
    fireEvent.click(screen.getByRole("button", { name: tr.spectrum.run }));
    expect(await screen.findByText(/1 nokta · 1 pozlamada ölçülemedi/)).toBeTruthy();
    expect(screen.getByText("Basit açıklık fotometrisi …")).toBeTruthy();
    expect(posted[0]).toEqual({ ra: 162.3, dec: -53.3, visit: 2, object_key: "luhman-16" });
  });

  it("status bar: says the archive date is being read, never invents one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          default: "dr1",
          releases: [
            { id: "dr1", label: "DR1", doi: null, notice: null },
            { id: "qr3", label: "QR3", doi: null, notice: null },
          ],
          archive: null,
          upstreams: [{ id: "irsa", label: "IRSA", state: "unknown" }],
        }),
      ),
    );
    render(<StatusBar />);
    expect(await screen.findByText(/DR1 \(varsayılan\) \+ QR3/)).toBeTruthy();
    expect(screen.getByText(tr.status.checking)).toBeTruthy();
  });
});
