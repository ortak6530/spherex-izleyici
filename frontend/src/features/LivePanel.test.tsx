import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import LivePanel from "./LivePanel";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const POS = {
  utc: "2026-11-14T07:23:00Z",
  ra: 269.4461,
  dec: 4.7707,
  method: "SIMBAD J2000 + öz hareket (paralaks ihmal)",
  moved_since_j2000_arcsec: 279.3,
  site: { name: "Ankara", lat: 39.9358, lon: 32.8387, source: "Wikidata Q3640" },
  sky: {
    alt_deg: 14.8,
    az_deg: 96.2,
    rise: { utc: "2026-11-15T05:54:21Z", az_deg: 85 },
    set: { utc: "2026-11-14T18:28:17Z", az_deg: 275 },
    transit: { utc: "2026-11-14T12:10:00Z", alt_deg: 54.8 },
    always_up: false,
    never_up: false,
    horizon: "0°",
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("live position", () => {
  it("never asks for the browser location; a picked city is sent by name", async () => {
    const geo = vi.fn();
    vi.stubGlobal("navigator", { ...navigator, geolocation: { getCurrentPosition: geo } });
    const posted: Array<Record<string, unknown>> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/live/cities"))
          return json({ cities: [{ name: "Ankara", lat: 39.9358, lon: 32.8387, wikidata: "Q3640" }] });
        if (url.endsWith("/live/start")) {
          posted.push(JSON.parse(init!.body as string));
          return json({ job_id: "lv1" });
        }
        return json({ status: "running", steps: [{ step: "position", position: POS }], result: null });
      }),
    );
    const target = {
      kind: "object",
      key: "barnard",
      name: "Barnard",
      query: "Barnard's Star",
      source: "x",
    } as const;
    render(<LivePanel target={target} />);
    expect(await screen.findByText(/17h57m47/)).toBeTruthy();
    expect(screen.getByText(/279\.3″/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(tr.live.mySky), { target: { value: "Ankara" } });
    expect(await screen.findByText(/Ufkun 15° üstünde, yön 96° \(D\)/)).toBeTruthy();
    expect(screen.getByText(/Doğuş:/)).toBeTruthy();
    expect(posted[0]).toEqual({ q: "Barnard's Star" });
    expect(posted.some((p) => p.city === "Ankara")).toBe(true);
    expect(geo).not.toHaveBeenCalled();
  });
});
