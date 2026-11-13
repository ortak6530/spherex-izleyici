import { Loader2, Search } from "lucide-react";
import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { apiGet, type Candidate, type ResolveResponse, type Target } from "../lib/api";
import { track } from "../lib/events";
import { errorText } from "../lib/format";

// Shareable links: ?q=<name or coordinates> runs the search on load
const INITIAL_Q = new URLSearchParams(window.location.search).get("q") ?? "";

/** A search started from elsewhere on the page (e.g. a collection card); `n` makes repeats distinct. */
export type SearchRequest = { q: string; n: number } | null;

export default function SearchBox({
  onTarget,
  request = null,
}: {
  onTarget: (t: Target) => void;
  request?: SearchRequest;
}) {
  const { t } = useTranslation();
  const inputId = useId();
  const [query, setQuery] = useState(INITIAL_Q);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);

  const resolve = async (q: string) => {
    const text = q.trim();
    if (!text) return;
    setBusy(true);
    setMessage(null);
    setCandidates([]);
    track("search_submitted", { payload: { length: text.length } });
    try {
      const r = await apiGet<ResolveResponse>(`/resolve?q=${encodeURIComponent(text)}`);
      if (r.target) {
        onTarget(r.target);
        const url = new URL(window.location.href);
        if (url.searchParams.get("q") !== text) {
          url.searchParams.set("q", text);
          ["d", "compare"].forEach((k) => url.searchParams.delete(k));
          window.history.replaceState(null, "", url);
        }
        setQuery(r.target.kind === "coordinate" ? text : r.target.name);
      } else {
        setCandidates(r.candidates ?? []);
        setMessage(
          r.candidates?.length
            ? t("search.suggestions")
            : r.upstream_unavailable?.length
              ? t("search.upstreamDown")
              : t("search.noResult"),
        );
      }
    } catch (e) {
      setMessage(errorText(t, e));
    } finally {
      setBusy(false);
    }
  };

  // Shareable links: run the ?q= search once on load (deferred so no state is set during the effect)
  useEffect(() => {
    if (!INITIAL_Q) return;
    const id = window.setTimeout(() => void resolve(INITIAL_Q), 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!request) return;
    const id = window.setTimeout(() => {
      setQuery(request.q);
      void resolve(request.q);
    }, 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request?.n]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void resolve(query);
  };

  return (
    <form
      onSubmit={onSubmit}
      role="search"
      className="relative order-last w-full lg:order-none lg:mx-4 lg:flex-1"
    >
      <label htmlFor={inputId} className="sr-only">
        {t("search.label")}
      </label>
      <div className="relative flex items-center">
        <Search className="pointer-events-none absolute left-3 size-5 text-ink-400" aria-hidden="true" />
        <input
          id={inputId}
          type="search"
          value={query}
          maxLength={100}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("search.placeholder")}
          className="h-11 w-full rounded-xl border border-white/10 bg-space-950/70 pr-24 pl-10 text-base text-ink-100 placeholder:text-ink-400 focus:border-nebula-400 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="absolute right-1.5 flex h-8 cursor-pointer items-center gap-1.5 rounded-lg bg-star-400 px-4 text-sm font-semibold text-space-950 transition-colors duration-200 hover:bg-star-300 disabled:cursor-wait disabled:opacity-70"
        >
          {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          {busy ? t("search.searching") : t("search.submit")}
        </button>
      </div>
      {(message || candidates.length > 0) && (
        <div
          role="status"
          className="glass absolute top-full right-0 left-0 z-40 mt-2 rounded-xl p-3 text-sm"
        >
          {message && <p className="text-warn-400">{message}</p>}
          {candidates.length > 0 && (
            <ul className="mt-2 space-y-1">
              {candidates.map((c) => (
                <li key={`${c.source}-${c.label}`}>
                  <button
                    type="button"
                    onClick={() => {
                      const q = c.main_id ?? c.label;
                      setQuery(c.label);
                      void resolve(q);
                    }}
                    className="flex w-full cursor-pointer items-baseline justify-between gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-white/10"
                  >
                    <span className="text-ink-100">{c.label}</span>
                    <span className="shrink-0 text-xs text-ink-400">
                      {c.otype ?? c.description ?? ""} · {c.source}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </form>
  );
}
