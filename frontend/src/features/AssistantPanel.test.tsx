import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import { lastComparison } from "../lib/lastComparison";
import AssistantPanel from "./AssistantPanel";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  lastComparison.set(null);
});

function mockApi(reply: object) {
  const posted: Array<Record<string, unknown>> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/assistant/quick"))
        return json({ items: [{ id: "interpret", label: "Karşılaştırmayı yorumla" }] });
      if (url.endsWith("/assistant/message")) {
        posted.push(JSON.parse(init!.body as string));
        return json({ job_id: "as1" });
      }
      if (url.endsWith("/jobs/as1"))
        return json({
          status: "done",
          steps: [
            { step: "assistant_chunk", text: "Kayma " },
            { step: "assistant_chunk", text: "12,50″." },
          ],
          result: reply,
        });
      return json({});
    }),
  );
  return posted;
}

describe("assistant panel", () => {
  it("shows the note, sends only the comparison id and renders the server's answer", async () => {
    const posted = mockApi({ text: "Kayma 12,50″.", source: "interpret", suggestions: [], action: null });
    lastComparison.set("ab12");
    const target = {
      kind: "object",
      key: "barnard",
      name: "Barnard's star",
      query: "Barnard",
      source: "x",
    } as const;
    render(<AssistantPanel target={target} onSearch={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: tr.assistant.open }));
    expect(screen.getByText(tr.assistant.note)).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Karşılaştırmayı yorumla" }));
    expect(await screen.findByText("Kayma 12,50″.")).toBeTruthy();
    expect(posted[0]).toMatchObject({ quick: "interpret", context: { comparison_id: "ab12" } });
    expect((posted[0].context as { object: { key: string } }).object.key).toBe("barnard");
  });

  it("opens an object the answer names", async () => {
    mockApi({
      text: "Andromeda Galaksisi açılıyor…",
      source: "open_object",
      suggestions: [],
      action: { type: "open_object", q: "M31" },
    });
    const onSearch = vi.fn();
    render(<AssistantPanel target={null} onSearch={onSearch} />);
    fireEvent.click(screen.getByRole("button", { name: tr.assistant.open }));
    fireEvent.change(screen.getByLabelText(tr.assistant.inputLabel), { target: { value: "andromeda" } });
    fireEvent.click(screen.getByRole("button", { name: tr.assistant.send }));
    await waitFor(() => expect(onSearch).toHaveBeenCalledWith("M31"));
  });
});
