import { ExternalLink, Loader2, Telescope } from "lucide-react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import ProgressLine from "../components/ProgressLine";
import { apiGet } from "../lib/api";
import { errorText } from "../lib/format";
import { runJob } from "../lib/jobs";

export type SsoisResult = {
  designation: string;
  status: "ok" | "not_found" | "not_covered";
  reason?: string;
  query?: string;
  range?: [string, string];
  total?: number;
  first?: string | null;
  last?: string | null;
  instruments?: [string, number][];
  n_instruments?: number;
  recent?: {
    date: string;
    instrument: string | null;
    filter: string | null;
    exptime_s: string | null;
    image: string | null;
    link: string | null;
  }[];
  source: string;
  note: string;
};

/** "Bu cismi başka hangi teleskoplar görmüş olabilir?" — CADC SSOIS, links only (no download). */
export default function OtherTelescopes({ designation, kind }: { designation: string; kind?: string }) {
  const { t } = useTranslation();
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<SsoisResult | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const q = kind ? `?kind=${encodeURIComponent(kind)}` : "";
      const r = await runJob<SsoisResult>(
        () => apiGet(`/moving/${encodeURIComponent(designation)}/ssois${q}`),
        () => setStep(t("ssois.searching")),
      );
      setRes(r);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
      setStep(null);
    }
  };

  return (
    <section className="glass space-y-3 rounded-2xl p-5" aria-labelledby={id}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={id} className="flex items-center gap-2 font-display text-lg font-semibold text-ink-100">
          <Telescope className="size-5 text-nebula-300" aria-hidden="true" />
          {t("ssois.title")}
        </h3>
        {!res && (
          <button
            type="button"
            onClick={() => void run()}
            disabled={busy}
            className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/15 px-3 text-sm text-ink-100 hover:border-white/30 disabled:cursor-wait disabled:opacity-60"
          >
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {t("ssois.run")}
          </button>
        )}
      </div>
      {!res && <p className="text-sm text-ink-300">{t("ssois.intro")}</p>}
      {step && <ProgressLine text={step} />}
      {error && (
        <p className="text-sm text-danger-400" role="alert">
          {error}
        </p>
      )}
      {res?.status === "not_covered" && <p className="text-sm text-warn-400">{t("ssois.comet")}</p>}
      {res?.status === "not_found" && (
        <p className="text-sm text-ink-300">{t("ssois.notFound", { q: res.query })}</p>
      )}
      {res?.status === "ok" && (
        <div className="space-y-3 text-sm">
          <p className="text-ink-100">
            {t("ssois.summary", {
              n: res.total,
              k: res.n_instruments,
              first: res.first,
              last: res.last,
            })}
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {res.instruments?.map(([name, n]) => (
              <li
                key={name}
                className="rounded-full border border-white/10 px-2.5 py-0.5 text-xs text-ink-300"
              >
                {name} · {n}
              </li>
            ))}
          </ul>
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-left text-xs">
              <caption className="pb-1 text-left text-ink-400">
                {t("ssois.recent", { n: res.recent?.length })}
              </caption>
              <thead className="text-ink-400">
                <tr>
                  <th className="py-1 pr-3">{t("ssois.date")}</th>
                  <th className="py-1 pr-3">{t("ssois.instrument")}</th>
                  <th className="py-1 pr-3">{t("ssois.filter")}</th>
                  <th className="py-1">{t("ssois.image")}</th>
                </tr>
              </thead>
              <tbody className="text-ink-100">
                {res.recent?.map((r, i) => (
                  <tr key={`${r.image}-${i}`} className="border-t border-white/5">
                    <td className="py-1 pr-3 font-mono">{r.date}</td>
                    <td className="py-1 pr-3">{r.instrument}</td>
                    <td className="py-1 pr-3">{r.filter ?? "—"}</td>
                    <td className="py-1 break-all">
                      {r.link ? (
                        <a
                          href={r.link}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="inline-flex items-center gap-1 text-nebula-300 hover:underline"
                        >
                          {r.image}
                          <ExternalLink className="size-3 shrink-0" aria-hidden="true" />
                        </a>
                      ) : (
                        r.image
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {res && (
        <p className="text-xs text-ink-400">
          {res.note} {t("ssois.source", { src: res.source })}
        </p>
      )}
    </section>
  );
}
