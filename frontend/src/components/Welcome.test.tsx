import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import { auth } from "../lib/auth";
import { entryChoice } from "../lib/entry";
import EntryGate from "./Welcome";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const USER = { email: "ayse@example.org", is_admin: false, created_at: null };

function mockApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/auth/me")) return json({ user: null, email_mode: "server_log" });
      if (url.endsWith("/auth/request-code"))
        return json({ ok: true, expires_in_s: 600, sends_left: 2, delivery: "server_log" }, 202);
      if (url.endsWith("/auth/verify")) return json({ user: USER });
      if (url.endsWith("/me/saved")) return json({ items: [] });
      return json({ ok: true });
    }),
  );
}

const site = () => <EntryGate>{<p>ANA ARAYÜZ</p>}</EntryGate>;

beforeEach(async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ok: true })),
  );
  await act(async () => {
    await auth.logout();
    auth.closeLogin();
  });
  vi.unstubAllGlobals();
  entryChoice.clear();
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("welcome screen", () => {
  it("guest: continue opens the site and the choice is remembered for the session", async () => {
    mockApi();
    render(site());
    expect(await screen.findByRole("heading", { name: tr.app.title })).toBeTruthy();
    expect(screen.getByText(tr.welcome.privacyLogin)).toBeTruthy();
    expect(screen.queryByText("ANA ARAYÜZ")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: tr.welcome.guest }));
    expect(screen.getByText("ANA ARAYÜZ")).toBeTruthy();

    cleanup();
    render(site()); // reload in the same session
    expect(screen.getByText("ANA ARAYÜZ")).toBeTruthy();
    expect(screen.queryByRole("button", { name: tr.welcome.guest })).toBeNull();
  });

  it("sign-in opens the site; signing out returns to the welcome screen", async () => {
    mockApi();
    render(site());
    fireEvent.click(await screen.findByRole("button", { name: tr.welcome.login }));
    fireEvent.change(screen.getByLabelText(tr.account.email), { target: { value: USER.email } });
    fireEvent.click(screen.getByRole("button", { name: tr.account.sendCode }));
    fireEvent.change(await screen.findByLabelText(tr.account.code), { target: { value: "123456" } });
    // jsdom has no modal <dialog>, so the page's own "Giriş yap" button is visible too
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: tr.account.verify }));
    expect(await screen.findByText("ANA ARAYÜZ")).toBeTruthy();

    await act(async () => {
      await auth.logout();
    });
    await waitFor(() => expect(screen.getByRole("button", { name: tr.welcome.guest })).toBeTruthy());
    expect(screen.queryByText("ANA ARAYÜZ")).toBeNull();
  });

  it("deep links skip the screen: object / shared comparison links and full pages", () => {
    mockApi();
    window.history.replaceState(null, "", "/?q=M31&d=5&compare=1");
    render(site());
    expect(screen.getByText("ANA ARAYÜZ")).toBeTruthy();
    cleanup();

    entryChoice.clear();
    window.history.replaceState(null, "", "/#admin");
    render(site());
    expect(screen.getByText("ANA ARAYÜZ")).toBeTruthy();
    cleanup();

    entryChoice.clear();
    window.history.replaceState(null, "", "/");
    render(<EntryGate bypass>{<p>ANA ARAYÜZ</p>}</EntryGate>); // App passes bypass while a page is open
    expect(screen.getByText("ANA ARAYÜZ")).toBeTruthy();
  });
});
