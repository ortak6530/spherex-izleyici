import { Database } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiGet } from "../lib/api";

type Upstream = {
  id: string;
  label: string;
  state: "ok" | "error" | "unknown";
  detail?: string;
  at?: string;
};
export type StatusResponse = {
  default: string;
  releases: { id: string; label: string; doi: string | null; notice: string | null }[];
  archive: {
    newest_utc: string;
    newest_release: string;
    per_release: Record<string, string>;
    checked_at: string;
    source: string;
  } | null;
  upstreams: Upstream[];
};

const REFRESH_MS = 60_000;
const DOT = { ok: "bg-ok-400", error: "bg-danger-400", unknown: "bg-ink-400/60" } as const;

function utc(iso: string, lang: string, withTime = false) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(lang === "tr" ? "tr-TR" : "en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

/** Thin bar under the top bar: active releases, the archive's newest observation, upstream states. */
export default function StatusBar() {
  const { t, i18n } = useTranslation();
  const [s, setS] = useState<StatusResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let stop = false;
    const load = () =>
      apiGet<StatusResponse>("/meta/status")
        .then((r) => !stop && (setS(r), setFailed(false)))
        .catch(() => !stop && setFailed(true));
    void load();
    const id = window.setInterval(load, REFRESH_MS);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, []);

  const lang = i18n.language;
  return (
    <div
      className="glass mx-3 mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl px-4 py-1.5 text-xs text-ink-300 sm:mx-4"
      aria-label={t("status.label")}
      role="status"
    >
      <span className="inline-flex items-center gap-1.5">
        <Database className="size-3.5 text-nebula-300" aria-hidden="true" />
        {t("status.releases")}:{" "}
        <strong className="font-medium text-ink-100">
          {s
            ? s.releases
                .map((r) => (r.id === s.default ? `${r.label} (${t("status.default")})` : r.label))
                .join(" + ")
            : failed
              ? t("status.unavailable")
              : t("status.loading")}
        </strong>
      </span>
      {s && (
        <span title={s.archive ? `${s.archive.source}` : undefined}>
          {t("status.newest")}:{" "}
          {s.archive ? (
            <>
              <strong className="font-medium text-ink-100">
                {utc(s.archive.newest_utc, lang)} ({s.archive.newest_release})
              </strong>
              <span className="text-ink-400">
                {" "}
                · {t("status.checked", { at: utc(s.archive.checked_at, lang, true) })}
              </span>
            </>
          ) : (
            <span className="text-ink-400">{t("status.checking")}</span>
          )}
        </span>
      )}
      {s && (
        <span className="inline-flex flex-wrap items-center gap-2.5">
          {s.upstreams.map((u) => (
            <span
              key={u.id}
              className="inline-flex items-center gap-1"
              title={
                u.state === "unknown"
                  ? t("status.notTried")
                  : `${t(`status.state.${u.state}`)} · ${u.detail ?? ""} · ${u.at ? utc(u.at, lang, true) : ""} UTC`
              }
            >
              <span className={`size-2 rounded-full ${DOT[u.state]}`} aria-hidden="true" />
              {u.label}
              <span className="sr-only">: {t(`status.state.${u.state}`)}</span>
            </span>
          ))}
        </span>
      )}
      {s?.releases
        .filter((r) => r.notice)
        .map((r) => (
          <span key={r.id} className="text-warn-400">
            {r.notice}
          </span>
        ))}
    </div>
  );
}
