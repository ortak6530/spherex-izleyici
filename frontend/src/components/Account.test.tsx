import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import tr from "../i18n/tr.json";
import { auth } from "../lib/auth";
import AccountButton from "./Account";
import SaveButton from "./SaveButton";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const USER = { email: "ayse@example.org", is_admin: false, created_at: null };

function mockApi(verifyAnswers: Response[]) {
  const calls: Array<{ url: string; body: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, body: init?.body ? JSON.parse(init.body as string) : null });
      if (url.endsWith("/auth/me")) return json({ user: null, email_mode: "server_log" });
      if (url.endsWith("/auth/request-code"))
        return json({ ok: true, expires_in_s: 600, sends_left: 2, delivery: "server_log" }, 202);
      if (url.endsWith("/auth/verify")) return verifyAnswers.shift()!;
      if (url.endsWith("/me/saved")) return json({ items: [] });
      return json({});
    }),
  );
  return calls;
}

beforeEach(async () => {
  // Start every test signed out (the auth store is a module singleton)
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ok: true })),
  );
  await act(async () => {
    await auth.logout();
    auth.closeLogin();
  });
  vi.unstubAllGlobals();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("sign-in with an e-mailed code", () => {
  it("asks for a code, reports wrong attempts, then signs in", async () => {
    const calls = mockApi([json({ code: "INVALID_CODE", attempts_left: 4 }, 400), json({ user: USER })]);
    render(<AccountButton />);
    fireEvent.click(await screen.findByRole("button", { name: tr.account.login }));
    fireEvent.change(screen.getByLabelText(tr.account.email), { target: { value: "ayse@example.org" } });
    fireEvent.click(screen.getByRole("button", { name: tr.account.sendCode }));
    expect(await screen.findByText(tr.account.devServerLog)).toBeTruthy();

    const codeBox = screen.getByLabelText(tr.account.code);
    fireEvent.change(codeBox, { target: { value: "12 34-56x" } });
    expect((codeBox as HTMLInputElement).value).toBe("123456"); // digits only
    fireEvent.click(screen.getByRole("button", { name: tr.account.verify }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      tr.account.errors.INVALID_CODE.replace("{{n}}", "4"),
    );

    fireEvent.click(screen.getByRole("button", { name: tr.account.verify }));
    await waitFor(() => expect(auth.get().user?.email).toBe("ayse@example.org"));
    expect(await screen.findByRole("button", { name: tr.account.myAccount })).toBeTruthy();
    const verifyBodies = calls.filter((c) => c.url.endsWith("/auth/verify")).map((c) => c.body);
    expect(verifyBodies).toEqual([
      { email: "ayse@example.org", code: "123456" },
      { email: "ayse@example.org", code: "123456" },
    ]);
  });
});

describe("SaveButton", () => {
  it("opens the sign-in dialog for signed-out visitors", async () => {
    mockApi([]);
    render(<SaveButton kind="object" refId="m-31" label="M 31" data={{ q: "M31" }} />);
    fireEvent.click(screen.getByRole("button", { name: tr.account.addToList }));
    expect(auth.get().loginOpen).toBe(true);
  });
});
