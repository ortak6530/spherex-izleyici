import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import { runMaybeJob } from "../lib/jobs";
import ProgressLine from "./ProgressLine";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("ProgressLine", () => {
  it("shows the step, the elapsed time, and a slow-archive note after 20 s", () => {
    vi.useFakeTimers();
    render(<ProgressLine text="Kesit alınıyor…" />);
    expect(screen.getByRole("status").textContent).toContain("Kesit alınıyor…");
    expect(screen.queryByText(tr.progress.slow)).toBeNull();
    act(() => vi.advanceTimersByTime(21_000));
    expect(screen.getByText("21 sn")).toBeTruthy();
    expect(screen.getByText(tr.progress.slow)).toBeTruthy();
  });
});

describe("runMaybeJob", () => {
  it("returns a cached answer directly", async () => {
    const r = await runMaybeJob(async () => ({ main_id: "M 31", from_cache: true }));
    expect(r).toEqual({ main_id: "M 31", from_cache: true });
  });

  it("follows a job id until the job is done (HTTP polling fallback)", async () => {
    const fetchMock = vi.fn<(url: string) => Promise<Response>>(
      async () =>
        new Response(
          JSON.stringify({
            id: "abcdef",
            kind: "object_info",
            status: "done",
            steps: [{ step: "info_query", elapsed_s: 0.1 }],
            result: { main_id: "M 31" },
            error: null,
          }),
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const steps: string[] = [];
    const r = await runMaybeJob<{ main_id: string }>(
      async () => ({ job_id: "abcdef" }),
      (s) => steps.push(s.step),
    );
    expect(r).toEqual({ main_id: "M 31" });
    expect(steps).toEqual(["info_query"]);
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/v1/jobs/abcdef");
  });
});
