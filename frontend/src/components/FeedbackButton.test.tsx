import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import type { Target } from "../lib/api";
import tr from "../i18n/tr.json";
import FeedbackButton from "./FeedbackButton";

const target: Target = { kind: "object", key: "m-31", name: "M 31", query: "M31", source: "test" };

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("FeedbackButton", () => {
  it("sends category, message and context, then thanks the visitor", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true, id: 1 }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<FeedbackButton target={target} />);
    fireEvent.click(screen.getAllByRole("button", { name: tr.feedback.button })[0]);
    fireEvent.click(screen.getByLabelText(tr.feedback.categories.bug));
    fireEvent.change(screen.getByLabelText(tr.feedback.message), {
      target: { value: "Kesit yüklenmedi." },
    });
    fireEvent.click(screen.getByRole("button", { name: tr.feedback.send }));
    await waitFor(() => expect(screen.getByText(tr.feedback.thanks)).toBeTruthy());
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/feedback");
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({
      category: "bug",
      message: "Kesit yüklenmedi.",
      object_key: "m-31",
      email: null,
    });
    expect(body.website).toBeNull();
  });

  it("does not send a too-short message", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<FeedbackButton target={null} />);
    fireEvent.click(screen.getAllByRole("button", { name: tr.feedback.button })[0]);
    fireEvent.change(screen.getByLabelText(tr.feedback.message), { target: { value: "ok" } });
    fireEvent.click(screen.getByRole("button", { name: tr.feedback.send }));
    expect(screen.getByRole("alert").textContent).toBe(tr.feedback.tooShort);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
