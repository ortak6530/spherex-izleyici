import { Crosshair, Loader2, Search } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  apiGet,
  type Candidate,
  type ResolveResponse,
  type Suggestion,
  type SuggestResponse,
  type Target,
} from "../lib/api";
import { track } from "../lib/events";
import { errorText } from "../lib/format";

// Shareable links: ?q=<name or coordinates> runs the search on load
const INITIAL_Q = new URLSearchParams(window.location.search).get("q") ?? "";
const MIN_CHARS = 2;
const DEBOUNCE_MS = 250;
const MAX_ITEMS = 8;

/** A search started from elsewhere on the page (e.g. a collection card); `n` makes repeats distinct. */
export type SearchRequest = { q: string; n: number } | null;

const SOURCE_LABEL: Record<string, string> = {
  local: "local",
  Sesame: "SIMBAD",
  SIMBAD: "SIMBAD",
  JPL: "JPL",
};

export default function SearchBox({
  onTarget,
  request = null,
}: {
  onTarget: (t: Target) => void;
  request?: SearchRequest;
}) {
  const { t } = useTranslation();
  const inputId = useId();
  const listId = useId();
  const [query, setQuery] = useState(INITIAL_Q);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  // Autocomplete (ARIA combobox): local list first (instant), then SIMBAD/JPL when they answer
  const [items, setItems] = useState<Suggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [unavailable, setUnavailable] = useState<string[]>([]);
  const typed = useRef(false); // only text typed by the person triggers suggestions
  const seq = useRef(0);

  const closeList = () => {
    setOpen(false);
    setActive(-1);
  };

  const resolve = async (q: string) => {
    const text = q.trim();
    if (!text) return;
    typed.current = false;
    seq.current++; // drop suggestion answers still in flight
    closeList();
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

  // Suggestions: 2+ characters, 250 ms after the last keystroke; stale answers are ignored
  useEffect(() => {
    if (!typed.current) return;
    const text = query.trim();
    const my = ++seq.current;
    if (text.length < MIN_CHARS) {
      const id = window.setTimeout(() => {
        if (my !== seq.current) return;
        setItems([]);
        closeList();
      }, 0);
      return () => window.clearTimeout(id);
    }
    const id = window.setTimeout(async () => {
      const q = encodeURIComponent(text);
      try {
        const fast = await apiGet<SuggestResponse>(`/suggest?q=${q}&local=1`);
        if (my !== seq.current) return;
        setItems(fast.items.slice(0, MAX_ITEMS));
        setOpen(true);
        setActive(-1);
        if (fast.items[0]?.kind === "coordinate") return; // nothing to add for coordinates
        setRemoteLoading(true);
        const full = await apiGet<SuggestResponse>(`/suggest?q=${q}`);
        if (my !== seq.current) return;
        setItems(full.items.slice(0, MAX_ITEMS));
        setUnavailable(full.unavailable);
        setOpen(true);
      } catch {
        // Suggestions are a convenience: on errors (rate limit, network) the plain search still works
      } finally {
        if (my === seq.current) setRemoteLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [query]);

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
      typed.current = false;
      setQuery(request.q);
      void resolve(request.q);
    }, 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request?.n]);

  const pick = (s: Suggestion) => {
    track("ui_action", { payload: { button: "suggestion", source: s.source } });
    typed.current = false;
    setQuery(s.kind === "coordinate" ? s.query : s.label);
    void resolve(s.query);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void resolve(query);
  };

  const showList = open && items.length > 0 && !message && candidates.length === 0;
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!items.length) return;
      e.preventDefault();
      setOpen(true);
      const n = items.length;
      setActive((a) => (e.key === "ArrowDown" ? (a + 1) % n : a <= 0 ? n - 1 : a - 1));
    } else if (e.key === "Enter" && showList && active >= 0) {
      e.preventDefault();
      pick(items[active]);
    } else if (e.key === "Escape") {
      if (showList) e.preventDefault();
      closeList();
      setMessage(null);
      setCandidates([]);
    } else if (e.key === "Tab") {
      closeList();
    }
  };

  const optionId = (i: number) => `${listId}-opt-${i}`;

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
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? optionId(active) : undefined}
          value={query}
          maxLength={100}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => {
            typed.current = true;
            setMessage(null);
            setCandidates([]);
            setQuery(e.target.value);
          }}
          onKeyDown={onKeyDown}
          onBlur={() => window.setTimeout(closeList, 120)}
          onFocus={() => items.length > 0 && query.trim().length >= MIN_CHARS && setOpen(true)}
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

      <div
        className={`glass-strong absolute top-full right-0 left-0 z-40 mt-2 rounded-xl p-1.5 text-sm ${showList ? "" : "hidden"}`}
      >
        <ul id={listId} role="listbox" aria-label={t("search.suggestLabel")}>
          {items.map((s, i) => (
            <li
              key={`${s.source}-${s.label}-${i}`}
              id={optionId(i)}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()} // keep focus in the input
              onClick={() => pick(s)}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-baseline justify-between gap-3 rounded-lg px-2.5 py-2 ${
                i === active ? "bg-white/10" : ""
              }`}
            >
              {s.kind === "coordinate" ? (
                <span className="flex items-center gap-2 text-ink-100">
                  <Crosshair className="size-4 text-nebula-300" aria-hidden="true" />
                  {t("search.searchHere", { q: s.label })}
                </span>
              ) : (
                <>
                  <span className="min-w-0 truncate text-ink-100">{s.label}</span>
                  <span className="shrink-0 text-xs text-ink-400">
                    {[s.detail, t(`search.source.${SOURCE_LABEL[s.source] ?? "local"}`)]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
        {(remoteLoading || unavailable.length > 0) && (
          <p className="flex items-center gap-1.5 px-2.5 pt-1 pb-1 text-xs text-ink-400" aria-live="polite">
            {remoteLoading && <Loader2 className="size-3 animate-spin" aria-hidden="true" />}
            {remoteLoading ? t("search.moreComing") : t("search.partial")}
          </p>
        )}
      </div>
      <span className="sr-only" aria-live="polite">
        {showList ? t("search.count", { count: items.length }) : ""}
      </span>

      {(message || candidates.length > 0) && (
        <div
          role="status"
          className="glass-strong absolute top-full right-0 left-0 z-40 mt-2 rounded-xl p-3 text-sm"
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
