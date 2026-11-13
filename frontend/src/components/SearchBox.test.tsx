import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import SearchBox from "./SearchBox";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const LOCAL = {
  items: [
    { kind: "name", label: "Barnard Yıldızı", query: "Barnard's Star", detail: "Yıldız", source: "local" },
  ],
  unavailable: [],
  partial: true,
};
const FULL = {
  items: [...LOCAL.items, { kind: "name", label: "Barnard  18", query: "Barnard  18", source: "SIMBAD" }],
  unavailable: [],
};

function mockFetch(handler: (url: string) => Response | Promise<Response>) {
  const f = vi.fn(async (url: string) => handler(url));
  vi.stubGlobal("fetch", f);
  return f;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SearchBox autocomplete", () => {
  it("shows local then remote suggestions and picks one with the keyboard", async () => {
    const f = mockFetch((url) => {
      if (url.includes("/suggest") && url.includes("local=1")) return json(LOCAL);
      if (url.includes("/suggest")) return json(FULL);
      return json({ kind: "not_found", candidates: [] });
    });
    render(<SearchBox onTarget={() => {}} />);
    const box = screen.getByRole("combobox");
    fireEvent.change(box, { target: { value: "barnard" } });
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(2));
    expect(box.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getAllByRole("option")[0].textContent).toContain("Barnard Yıldızı");

    fireEvent.keyDown(box, { key: "ArrowDown" });
    const first = screen.getAllByRole("option")[0];
    expect(first.getAttribute("aria-selected")).toBe("true");
    expect(box.getAttribute("aria-activedescendant")).toBe(first.id);
    fireEvent.keyDown(box, { key: "Enter" });
    await waitFor(() =>
      expect(f.mock.calls.some(([u]) => String(u).includes("/resolve?q=Barnard's%20Star"))).toBe(true),
    );
  });

  it("offers 'search at these coordinates' for coordinate input", async () => {
    mockFetch(() =>
      json({ items: [{ kind: "coordinate", label: "10.68 41.27", query: "10.68 41.27", source: "input" }] }),
    );
    render(<SearchBox onTarget={() => {}} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "10.68 41.27" } });
    const opt = await screen.findByRole("option");
    expect(opt.textContent).toBe(tr.search.searchHere.replace("{{q}}", "10.68 41.27"));
  });

  it("keeps the local list when the remote sources fail, and closes with Escape", async () => {
    mockFetch((url) => (url.includes("local=1") ? json(LOCAL) : json({ code: "INTERNAL_ERROR" }, 500)));
    render(<SearchBox onTarget={() => {}} />);
    const box = screen.getByRole("combobox");
    fireEvent.change(box, { target: { value: "barnard" } });
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(1));
    fireEvent.keyDown(box, { key: "Escape" });
    expect(box.getAttribute("aria-expanded")).toBe("false");
  });

  it("does not ask for suggestions below two characters", async () => {
    const f = mockFetch(() => json(LOCAL));
    render(<SearchBox onTarget={() => {}} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "b" } });
    await new Promise((r) => setTimeout(r, 350));
    expect(f).not.toHaveBeenCalled();
  });
});
