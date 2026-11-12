import { Database, Languages, Search } from "lucide-react";
import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { setLang } from "../i18n";
import { apiGet, type ReleasesResponse } from "../lib/api";
import { track } from "../lib/events";

function ReleaseBadge() {
  const { t } = useTranslation();
  const [data, setData] = useState<ReleasesResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    apiGet<ReleasesResponse>("/meta/releases", ctrl.signal)
      .then(setData)
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setError(true);
      });
    return () => ctrl.abort();
  }, []);

  const label = data?.releases.find((r) => r.id === data.default)?.label;
  return (
    <div className="hidden items-center gap-2 text-sm text-ink-300 lg:flex" aria-live="polite">
      <Database className="size-4 text-nebula-400" aria-hidden="true" />
      <span>
        {t("release.label")}:{" "}
        <strong className="font-medium text-ink-100">
          {error ? t("release.unavailable") : (label ?? t("release.loading"))}
        </strong>
        {data && (
          <>
            {" · "}
            {t("release.lastUpdate")}: {data.last_update ?? t("release.never")}
          </>
        )}
      </span>
    </div>
  );
}

export default function TopBar() {
  const { t, i18n } = useTranslation();
  const inputId = useId();
  const [query, setQuery] = useState("");
  const [note, setNote] = useState<string | null>(null);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    track("search_submitted", { payload: { length: query.trim().length, connected: false } });
    setNote(t("search.notConnected"));
  };

  return (
    <header className="glass sticky top-3 z-30 mx-3 mt-3 rounded-2xl px-4 py-3 sm:mx-4">
      <div className="flex flex-wrap items-center gap-3 lg:flex-nowrap">
        <a href="/" className="flex shrink-0 items-center gap-2.5 rounded-lg" aria-label={t("app.title")}>
          <img src="/favicon.svg" alt="" className="size-8" />
          <span className="font-display text-lg font-semibold tracking-wide text-ink-100">
            {t("app.title")}
          </span>
        </a>

        <form onSubmit={onSubmit} role="search" className="order-last w-full lg:order-none lg:mx-4 lg:flex-1">
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
              onChange={(e) => {
                setQuery(e.target.value);
                setNote(null);
              }}
              placeholder={t("search.placeholder")}
              className="h-11 w-full rounded-xl border border-white/10 bg-space-950/70 pr-24 pl-10 text-base text-ink-100 placeholder:text-ink-400 focus:border-nebula-400 focus:outline-none"
            />
            <button
              type="submit"
              className="absolute right-1.5 h-8 cursor-pointer rounded-lg bg-star-400 px-4 text-sm font-semibold text-space-950 transition-colors duration-200 hover:bg-star-300"
            >
              {t("search.submit")}
            </button>
          </div>
          {note && (
            <p role="status" className="mt-2 text-sm text-warn-400">
              {note}
            </p>
          )}
        </form>

        <div className="ml-auto flex items-center gap-3">
          <ReleaseBadge />
          <button
            type="button"
            onClick={() => setLang(i18n.language === "tr" ? "en" : "tr")}
            className="flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 px-3 text-sm text-ink-300 transition-colors duration-200 hover:border-white/25 hover:text-ink-100"
          >
            <Languages className="size-4" aria-hidden="true" />
            {t("lang.switch")}
          </button>
        </div>
      </div>
    </header>
  );
}
