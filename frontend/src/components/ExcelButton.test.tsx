import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import ExcelButton from "./ExcelButton";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Excel download", () => {
  it("starts the export job with the object and band, then fetches the file", async () => {
    const posted: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/export/xlsx")) {
          posted.push(JSON.parse(init!.body as string));
          return json({ job_id: "j1" });
        }
        if (url.endsWith("/jobs/j1"))
          return json({
            status: "done",
            steps: [],
            result: { file_id: "f1", filename: "m-31_2026-11-14.xlsx", size_bytes: 10, rows: {} },
          });
        return json({});
      }),
    );
    const clicked: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(`${this.getAttribute("href")}|${this.download}`);
    });
    render(<ExcelButton items={[{ q: "M 31", d: 5 }]} />);
    fireEvent.click(screen.getByRole("button", { name: tr.export.button }));
    await waitFor(() => expect(clicked).toEqual(["/api/v1/export/f1|m-31_2026-11-14.xlsx"]));
    expect(posted).toEqual([{ items: [{ q: "M 31", d: 5 }] }]);
  });

  it("explains the guest limit in Turkish", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ code: "LOGIN_REQUIRED_MULTI" }, 401)),
    );
    render(<ExcelButton items={[{ q: "M 31" }, { q: "M 33" }]} />);
    fireEvent.click(screen.getByRole("button", { name: tr.export.button }));
    expect((await screen.findByRole("alert")).textContent).toBe(tr.errors.LOGIN_REQUIRED_MULTI);
  });
});
