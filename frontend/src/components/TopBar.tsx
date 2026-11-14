import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import { setLang } from "../i18n";
import type { Target } from "../lib/api";
import AccountButton from "./Account";
import FeedbackButton from "./FeedbackButton";
import SearchBox, { type SearchRequest } from "./SearchBox";

// The data release / archive status now lives in StatusBar (under the top bar, on every width)

export default function TopBar({
  onTarget,
  searchRequest = null,
  target = null,
}: {
  onTarget: (t: Target) => void;
  searchRequest?: SearchRequest;
  target?: Target | null;
}) {
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
        <SearchBox onTarget={onTarget} request={searchRequest} />
        <div className="ml-auto flex items-center gap-3">
          <FeedbackButton target={target} />
          <AccountButton />
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
