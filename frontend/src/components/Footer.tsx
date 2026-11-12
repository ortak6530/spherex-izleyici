import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { realtime, type WsStatus } from "../lib/realtime";

function LiveStatus() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<WsStatus>("closed");
  useEffect(() => realtime.onStatus(setStatus), []);
  const color = status === "open" ? "bg-ok-400" : status === "connecting" ? "bg-warn-400" : "bg-ink-400";
  const label =
    status === "open"
      ? t("footer.liveOn")
      : status === "connecting"
        ? t("footer.liveConnecting")
        : t("footer.liveOff");
  return (
    <span className="inline-flex items-center gap-1.5" aria-live="polite">
      <span className={`size-2 rounded-full ${color}`} aria-hidden="true" />
      {t("footer.live")}: {label}
    </span>
  );
}

export default function Footer({ onSources, onPrivacy }: { onSources: () => void; onPrivacy: () => void }) {
  const { t } = useTranslation();
  return (
    <footer className="mx-3 mb-3 flex flex-col gap-2 rounded-2xl px-4 py-3 text-xs text-ink-400 sm:mx-4 md:flex-row md:items-center md:justify-between">
      <p className="italic">{t("footer.simulation")}</p>
      <p className="text-ink-300">{t("footer.data")}</p>
      <div className="flex items-center gap-4">
        <LiveStatus />
        <button type="button" onClick={onSources} className="cursor-pointer text-nebula-300 hover:underline">
          {t("footer.sources")}
        </button>
        <button type="button" onClick={onPrivacy} className="cursor-pointer text-nebula-300 hover:underline">
          {t("footer.privacy")}
        </button>
      </div>
    </footer>
  );
}
