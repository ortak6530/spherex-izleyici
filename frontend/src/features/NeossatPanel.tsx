import { ExternalLink, Loader2, Satellite } from "lucide-react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import ProgressLine from "../components/ProgressLine";
import { apiPost, type Target } from "../lib/api";
import { errorText, fmt } from "../lib/format";
import { runJob } from "../lib/jobs";

export type NeossatResult = {
  items: {
    observation_id: string;
    date_utc: string | null;
    exposure_s: number | null;
    product: string;
    raw_warning: boolean;
    target_name: string | null;
    preview?: string;
    fits?: string;
  }[];
  n_observations: number;
  truncated: boolean;
  source: string;
  note: string;
};

/** NEOSSat (CSA) frames containing the target, from CADC; links and previews only. */
export default function NeossatPanel({ target }: { target: Target }) {
  const { t } = useTranslation();
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<NeossatResult | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setRes(
        await runJob<NeossatResult>(() =>
          apiPost("/sky/neossat", { ra: target.ra, dec: target.dec, object_key: target.key }),
        ),
      );
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="glass space-y-3 rounded-2xl p-5" aria-labelledby={id}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={id} className="flex items-center gap-2 font-display text-lg font-semibold text-ink-100">
          <Satellite className="size-5 text-nebula-300" aria-hidden="true" />
          {t("neossat.title")}
        </h3>
        {!res && (
          <button
            type="button"
            onClick={() => void run()}
            disabled={busy}
            className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/15 px-3 text-sm text-ink-100 hover:border-white/30 disabled:cursor-wait disabled:opacity-60"
          >
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {t("neossat.run")}
          </button>
        )}
      </div>
      {!res && <p className="text-sm text-ink-300">{t("neossat.intro")}</p>}
      {busy && <ProgressLine text={t("neossat.searching")} />}
      {error && (
        <p className="text-sm text-danger-400" role="alert">
          {error}
        </p>
      )}
      {res && res.items.length === 0 && <p className="text-sm text-ink-300">{t("neossat.none")}</p>}
      {res && res.items.length > 0 && (
        <div className="space-y-2 text-sm">
          <p className="text-ink-100">
            {t(res.truncated ? "neossat.countAtLeast" : "neossat.count", {
              n: res.n_observations,
              shown: res.items.length,
            })}
          </p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {res.items.map((o) => (
              <li key={o.observation_id} className="flex gap-2 rounded-lg border border-white/10 p-2">
                {o.preview ? (
                  <a href={o.preview} target="_blank" rel="noreferrer noopener" className="shrink-0">
                    <img
                      src={o.preview}
                      alt={t("neossat.previewAlt", { id: o.observation_id })}
                      loading="lazy"
                      className="size-16 rounded object-cover"
                    />
                  </a>
                ) : null}
                <div className="min-w-0 text-xs">
                  <p className="font-mono text-ink-100">{o.date_utc?.replace("T", " ").slice(0, 16)} UTC</p>
                  <p className="text-ink-300">
                    {o.product.toUpperCase()}
                    {o.raw_warning ? ` · ${t("neossat.raw")}` : ""} · {fmt(o.exposure_s, 1)} s
                  </p>
                  {o.target_name && <p className="truncate text-ink-400">{o.target_name}</p>}
                  {o.fits && (
                    <a
                      href={o.fits}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1 text-nebula-300 hover:underline"
                    >
                      FITS <ExternalLink className="size-3" aria-hidden="true" />
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {res && (
        <p className="text-xs text-ink-400">
          {res.note} {t("neossat.source", { src: res.source })}
        </p>
      )}
    </section>
  );
}
