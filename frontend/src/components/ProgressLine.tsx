import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const SLOW_AFTER_S = 20;

/**
 * Live status of a slow server job: the latest step (sent over WebSocket, or polled over HTTP when the
 * socket is down), how long it has been running, and a calm note when the archive is slow (IRSA cutouts
 * often take 30-60 s). Mount it only while the job runs; the clock starts at mount.
 */
export default function ProgressLine({ text, className = "" }: { text: string; className?: string }) {
  const { t } = useTranslation();
  const [started] = useState(() => Date.now());
  const [now, setNow] = useState(started);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const s = Math.floor((now - started) / 1000);
  return (
    <div className={`text-sm ${className}`} role="status" aria-live="polite">
      <p className="flex items-center gap-2 text-nebula-300">
        <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden="true" />
        <span>{text}</span>
        {s >= 2 && (
          <span className="font-mono text-xs text-ink-400" aria-hidden="true">
            {t("progress.elapsed", { s })}
          </span>
        )}
      </p>
      {s >= SLOW_AFTER_S && <p className="mt-1 text-xs text-ink-400">{t("progress.slow")}</p>}
    </div>
  );
}
