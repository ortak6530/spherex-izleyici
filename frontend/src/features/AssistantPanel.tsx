import { Bot, Send, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { apiGet, apiPost, type Target } from "../lib/api";
import { errorText } from "../lib/format";
import { runJob } from "../lib/jobs";
import { lastComparison } from "../lib/lastComparison";

type Suggestion = { id: string; label: string };
type Reply = {
  text: string;
  source: string;
  suggestions: Suggestion[];
  action: { type: "open_object"; q: string } | null;
};
type Msg = { id: number; role: "user" | "bot"; text: string; suggestions?: Suggestion[]; typing?: boolean };

let nextId = 1;

/** Right-hand drawer: rule-based assistant. Answers stream over WS (job steps); HTTP polling is the fallback. */
export default function AssistantPanel({
  target,
  onSearch,
}: {
  target: Target | null;
  onSearch: (q: string) => void;
}) {
  const { t } = useTranslation();
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [quick, setQuick] = useState<Suggestion[]>([]);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open || quick.length) return;
    apiGet<{ items: Suggestion[] }>("/assistant/quick")
      .then((r) => setQuick(r.items))
      .catch(() => setQuick([]));
  }, [open, quick.length]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    listRef.current?.scrollTo?.({ top: listRef.current.scrollHeight });
  }, [msgs]);

  const patchBot = (id: number, patch: Partial<Msg>) =>
    setMsgs((m) => m.map((x) => (x.id === id ? { ...x, ...patch } : x)));

  const ask = async (body: { message?: string; quick?: string }, shown: string) => {
    if (busy) return;
    const botId = nextId++;
    setMsgs((m) => [
      ...m,
      { id: nextId++, role: "user", text: shown },
      { id: botId, role: "bot", text: "", typing: true },
    ]);
    setBusy(true);
    let streamed = "";
    try {
      const context = {
        object: target
          ? {
              key: target.key,
              name: target.name,
              query: target.query,
              kind: target.kind,
              otype: target.otype ?? null,
              main_id: target.main_id ?? null,
              designation: target.designation ?? null,
              orbit_class: target.orbit_class ?? null,
            }
          : null,
        comparison_id: lastComparison.get(),
      };
      const r = await runJob<Reply>(
        () => apiPost("/assistant/message", { ...body, context }),
        (s) => {
          if (s.step !== "assistant_chunk" || typeof s.text !== "string") return;
          streamed += s.text;
          patchBot(botId, { text: streamed });
        },
      );
      patchBot(botId, { text: r.text, suggestions: r.suggestions, typing: false });
      if (r.action?.type === "open_object") onSearch(r.action.q);
    } catch (e) {
      patchBot(botId, { text: errorText(t, e), typing: false });
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const m = text.trim();
    if (!m) return;
    setText("");
    void ask({ message: m }, m);
  };

  const chip =
    "cursor-pointer rounded-full border border-white/15 px-3 py-1.5 text-xs text-ink-100 transition-colors duration-200 hover:border-nebula-400 hover:bg-nebula-500/15 disabled:cursor-wait disabled:opacity-60";

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed right-4 bottom-4 z-40 inline-flex h-12 cursor-pointer items-center gap-2 rounded-full bg-nebula-500 px-5 text-sm font-medium text-white shadow-lg shadow-black/40 transition-colors duration-200 hover:bg-nebula-600"
        >
          <Bot className="size-5" aria-hidden="true" />
          {t("assistant.open")}
        </button>
      )}
      {open && (
        <aside
          aria-labelledby={titleId}
          className="glass-strong fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-white/10 sm:w-[24rem]"
        >
          <header className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-3">
            <h2
              id={titleId}
              className="flex items-center gap-2 font-display text-lg font-semibold text-ink-100"
            >
              <Bot className="size-5 text-nebula-300" aria-hidden="true" />
              {t("assistant.title")}
            </h2>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={t("assistant.close")}
              className="grid size-10 cursor-pointer place-items-center rounded-lg hover:bg-white/10"
            >
              <X className="size-5" aria-hidden="true" />
            </button>
          </header>
          <p className="border-b border-white/10 px-4 py-2 text-xs text-ink-400">{t("assistant.note")}</p>

          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3" aria-live="polite">
            {msgs.length === 0 && <p className="text-sm text-ink-300">{t("assistant.intro")}</p>}
            {msgs.map((m) => (
              <div key={m.id} className={m.role === "user" ? "flex justify-end" : "space-y-2"}>
                <div
                  className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm whitespace-pre-line ${
                    m.role === "user" ? "bg-nebula-500/80 text-white" : "bg-space-950/70 text-ink-100"
                  }`}
                >
                  {m.text}
                  {m.typing && (
                    <span className="text-ink-400" role="status">
                      {m.text ? " …" : t("assistant.typing")}
                    </span>
                  )}
                </div>
                {m.suggestions && m.suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {m.suggestions.map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        disabled={busy}
                        onClick={() => void ask({ quick: s.id }, s.label)}
                        className={chip}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {quick.length > 0 && (
            <div className="flex flex-wrap gap-1.5 border-t border-white/10 px-4 py-2">
              {quick.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  disabled={busy}
                  onClick={() => void ask({ quick: q.id }, q.label)}
                  className={chip}
                >
                  {q.label}
                </button>
              ))}
            </div>
          )}
          <form onSubmit={submit} className="flex gap-2 border-t border-white/10 px-4 py-3">
            <label htmlFor={`${titleId}-in`} className="sr-only">
              {t("assistant.inputLabel")}
            </label>
            <input
              id={`${titleId}-in`}
              ref={inputRef}
              value={text}
              maxLength={500}
              onChange={(e) => setText(e.target.value)}
              placeholder={t("assistant.placeholder")}
              className="h-11 min-w-0 flex-1 rounded-lg border border-white/10 bg-space-950/70 px-3 text-base text-ink-100 focus:border-nebula-400 focus:outline-none"
            />
            <button
              type="submit"
              disabled={busy || !text.trim()}
              aria-label={t("assistant.send")}
              className="grid size-11 cursor-pointer place-items-center rounded-lg bg-nebula-500 text-white hover:bg-nebula-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Send className="size-5" aria-hidden="true" />
            </button>
          </form>
        </aside>
      )}
    </>
  );
}
