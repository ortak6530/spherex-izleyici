import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import { auth } from "../lib/auth";
import { realtime } from "../lib/realtime";
import AdminPage from "./AdminPage";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

function mockApi(user: { email: string; is_admin: boolean }) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/auth/me"))
        return json({ user: { ...user, created_at: null }, email_mode: "emailjs" });
      if (url.endsWith("/me/saved")) return json({ items: [] });
      if (url.endsWith("/admin/summary"))
        return json({
          users: 3,
          events_24h: 12,
          events_24h_by_type: { search: 7, compare_time: 5 },
          sessions_24h: 4,
          feedback_new: 1,
          email_mode: "emailjs",
          note: "not",
        });
      if (url.includes("/admin/events"))
        return json({
          items: [
            { id: 1, ts: "2026-11-14T00:00:00", type: "search", object_key: "m-31", session: "abc123" },
          ],
        });
      return json({});
    }),
  );
}

// The realtime client has no public way to inject frames; tests reach its handler set directly
const emit = (m: Record<string, unknown>) =>
  (realtime as unknown as { handlers: Set<(m: Record<string, unknown>) => void> }).handlers.forEach((h) =>
    h(m),
  );

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AdminPage", () => {
  it("explains that only the admin account can open it", async () => {
    mockApi({ email: "biri@example.org", is_admin: false });
    await act(() => auth.load());
    render(<AdminPage onBack={() => {}} />);
    expect(screen.getByText(tr.admin.notAdmin)).toBeTruthy();
    expect(screen.queryByRole("tablist")).toBeNull();
  });

  it("shows the summary and puts live events on top of the list", async () => {
    mockApi({ email: "yonetici@example.org", is_admin: true });
    await act(() => auth.load());
    render(<AdminPage onBack={() => {}} />);
    expect(await screen.findByText("12")).toBeTruthy(); // events in 24 h
    fireEvent.click(screen.getByRole("tab", { name: tr.admin.tabs.live }));
    expect(await screen.findByText("m-31")).toBeTruthy();
    act(() =>
      emit({
        type: "admin_event",
        kind: "event",
        ts: "2026-11-14T00:01:00Z",
        event_type: "compare_time",
        object_key: "barnard",
      }),
    );
    act(() =>
      emit({
        type: "admin_event",
        kind: "feedback",
        ts: "2026-11-14T00:02:00Z",
        object_key: "m-42",
        category: "bug",
      }),
    );
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows[1].textContent).toContain("feedback");
    expect(rows[1].textContent).toContain("m-42");
    expect(rows[2].textContent).toContain("compare_time"); // its own type, not "admin_event"
    expect(rows[2].textContent).toContain("barnard");
    expect(rows[3].textContent).toContain("m-31"); // the HTTP-loaded history stays below
  });
});
