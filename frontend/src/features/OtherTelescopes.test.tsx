import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import OtherTelescopes from "./OtherTelescopes";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mock(result: object) {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      urls.push(url);
      if (url.includes("/ssois")) return json({ job_id: "ss1" });
      return json({ status: "done", steps: [], result });
    }),
  );
  return urls;
}

describe("other telescopes (CADC SSOIS)", () => {
  it("lists frames with a summary, links only for https, and the 'not necessarily visible' note", async () => {
    const urls = mock({
      designation: "433",
      status: "ok",
      query: "433",
      total: 7283,
      first: "2002-09-27",
      last: "2025-10-06",
      instruments: [["LCO/lsc_0m4a_kb29", 2369]],
      n_instruments: 40,
      recent: [
        {
          date: "2025-10-06",
          instrument: "ALMA",
          filter: "Band-7",
          exptime_s: "1034",
          image: "a1",
          link: null,
        },
        {
          date: "2024-01-01",
          instrument: "CFHT/MegaCam",
          filter: "r",
          exptime_s: "60",
          image: "c3",
          link: "https://x.org/c3",
        },
      ],
      source: "CADC SSOIS (bynameCADC)",
      note: "SSOIS, cismin öngörülen konumunun görüntü alanına düştüğü arşiv karelerini listeler; cismin o karede görünür (yeterince parlak) olduğu anlamına gelmez.",
    });
    render(<OtherTelescopes designation="433" kind="an" />);
    fireEvent.click(screen.getByRole("button", { name: tr.ssois.run }));
    expect(
      await screen.findByText(/7283 arşiv karesi, 40 farklı teleskop\/alet, 2002-09-27 – 2025-10-06/),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: /c3/ }).getAttribute("href")).toBe("https://x.org/c3");
    expect(screen.queryByRole("link", { name: /a1/ })).toBeNull();
    expect(screen.getByText(/görünür \(yeterince parlak\) olduğu anlamına gelmez/)).toBeTruthy();
    expect(urls[0]).toContain("/moving/433/ssois?kind=an");
  });

  it("explains that comets are not covered", async () => {
    mock({
      designation: "2025 N1",
      status: "not_covered",
      reason: "comet",
      source: "CADC SSOIS (bynameCADC)",
      note: "n",
    });
    render(<OtherTelescopes designation="2025 N1" kind="cu" />);
    fireEvent.click(screen.getByRole("button", { name: tr.ssois.run }));
    expect(await screen.findByText(/yalnızca asteroitleri kapsıyor/)).toBeTruthy();
  });
});
