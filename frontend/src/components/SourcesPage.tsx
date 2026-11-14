import { ArrowLeft, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiGet, type Attribution } from "../lib/api";

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="inline-flex items-center gap-1 break-all text-nebula-300 underline-offset-2 hover:underline"
    >
      {children}
      <ExternalLink className="size-3 shrink-0" aria-hidden="true" />
    </a>
  );
}

function SourceCard({ a }: { a: Attribution }) {
  const { t } = useTranslation();
  const planned = a.status === "planned";
  return (
    <li className="rounded-xl border border-white/10 bg-space-950/50 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-display text-lg font-semibold text-ink-100">{a.title}</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            planned ? "border border-warn-400/40 text-warn-400" : "border border-ok-400/40 text-ok-400"
          }`}
        >
          {planned ? t("sources.planned") : t("sources.used")}
        </span>
      </div>
      {a.purpose && <p className="mt-1 text-sm text-ink-300">{a.purpose}</p>}
      {a.text && (
        <figure className="mt-3">
          {/* Acknowledgements are quoted verbatim in the provider's English original, never translated */}
          <blockquote lang="en" className="border-l-2 border-nebula-400/60 pl-3 text-sm text-ink-100">
            {a.text}
          </blockquote>
          {a.text_source && (
            <figcaption className="mt-1 text-xs text-ink-400">
              {t("sources.textFrom")}{" "}
              {a.text_source.startsWith("http") ? (
                <Ext href={a.text_source}>{a.text_source}</Ext>
              ) : (
                a.text_source
              )}
              {a.verified && ` · ${t("sources.verified", { date: a.verified })}`}
            </figcaption>
          )}
        </figure>
      )}
      {a.note && <p className="mt-2 text-xs text-ink-400">{a.note}</p>}
      {a.license && (
        <p className="mt-2 text-sm">
          <span className="text-ink-400">{t("sources.license")}: </span>
          <span className="text-ink-300">{a.license}</span>
        </p>
      )}
      {a.dois && <p className="mt-1 font-mono text-xs text-ink-400">DOI: {a.dois.join(" · ")}</p>}
      {a.citations && a.citations.length > 0 && (
        <div className="mt-2 text-sm">
          <p className="text-ink-400">{t("sources.cite")}</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {a.citations.map((c) => (
              <li key={c.label}>
                <Ext href={c.url}>{c.label}</Ext>
              </li>
            ))}
          </ul>
        </div>
      )}
      {a.references && a.references.length > 0 && (
        <div className="mt-2 text-sm">
          <p className="text-ink-400">{t("sources.references")}</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {a.references.map((r) => (
              <li key={r.url}>
                <Ext href={r.url}>{r.label}</Ext>
              </li>
            ))}
          </ul>
        </div>
      )}
      {a.url && (
        <p className="mt-2 text-xs">
          <Ext href={a.url}>{a.url}</Ext>
        </p>
      )}
    </li>
  );
}

/** "Kaynaklar" page (#kaynaklar): every external resource with its verbatim acknowledgement. */
export default function SourcesPage({ onBack }: { onBack: () => void }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<Attribution[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    apiGet<{ items: Attribution[] }>("/meta/attributions")
      .then((r) => setItems(r.items))
      .catch(() => setFailed(true));
  }, []);

  const groups: Array<{ key: Attribution["group"]; title: string }> = [
    { key: "data", title: t("sources.data") },
    { key: "software", title: t("sources.software") },
  ];

  return (
    <section
      className="glass w-full max-w-4xl space-y-5 rounded-2xl p-5 sm:p-8"
      aria-labelledby="sources-title"
    >
      <button
        type="button"
        onClick={onBack}
        className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-ink-300 hover:text-ink-100"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> {t("sources.back")}
      </button>
      <div>
        <h1 id="sources-title" className="font-display text-3xl font-semibold text-ink-100">
          {t("sources.title")}
        </h1>
        <p className="mt-2 max-w-prose text-sm text-ink-300">{t("sources.intro")}</p>
      </div>
      {failed && (
        <p className="text-sm text-warn-400" role="alert">
          {t("sources.failed")}
        </p>
      )}
      {groups.map((g) => {
        const list = (items ?? []).filter((a) => (a.group ?? "data") === g.key);
        if (!list.length) return null;
        return (
          <div key={g.key} className="space-y-3">
            <h2 className="font-display text-xl font-semibold text-ink-100">{g.title}</h2>
            <ul className="space-y-3">
              {list.map((a) => (
                <SourceCard key={a.key} a={a} />
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}
