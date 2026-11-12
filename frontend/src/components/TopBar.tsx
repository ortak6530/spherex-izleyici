import { Database, Languages } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { setLang } from "../i18n";
import { apiGet, type ReleasesResponse, type Target } from "../lib/api";
import SearchBox from "./SearchBox";

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
  const extra = data?.releases
    .filter((r) => r.status === "active" && r.id !== data.default)
    .map((r) => r.label);
  return (
    <div className="hidden items-center gap-2 text-sm text-ink-300 xl:flex" aria-live="polite">
      <Database className="size-4 text-nebula-400" aria-hidden="true" />
      <span>
        {t("release.label")}:{" "}
        <strong className="font-medium text-ink-100">
          {error ? t("release.unavailable") : (label ?? t("release.loading"))}
        </strong>
        {extra && extra.length > 0 && <span className="text-ink-400"> (+{extra.join(", ")})</span>}
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

export default function TopBar({ onTarget }: { onTarget: (t: Target) => void }) {
  const { t, i18n } = useTranslation();
  return (
    <header className="glass sticky top-3 z-30 mx-3 mt-3 rounded-2xl px-4 py-3 sm:mx-4">
      <div className="flex flex-wrap items-center gap-3 lg:flex-nowrap">
        <a href="/" className="flex shrink-0 items-center gap-2.5 rounded-lg" aria-label={t("app.title")}>
          <img src="/favicon.svg" alt="" className="size-8" />
          <span className="font-display text-lg font-semibold tracking-wide text-ink-100">
            {t("app.title")}
          </span>
        </a>
        <SearchBox onTarget={onTarget} />
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
