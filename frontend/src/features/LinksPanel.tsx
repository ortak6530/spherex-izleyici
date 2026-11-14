import { ExternalLink, Link2 } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiGet } from "../lib/api";

type Link = { key: string; label: string; purpose: string; url: string; verified: string };

/** "Dış bağlantılar": IRSA's own SPHEREx tools and documents (from config/attributions.toml [[link]]). */
export default function LinksPanel() {
  const { t } = useTranslation();
  const id = useId();
  const [links, setLinks] = useState<Link[]>([]);

  useEffect(() => {
    apiGet<{ items: Link[] }>("/meta/links")
      .then((r) => setLinks(r.items))
      .catch(() => setLinks([]));
  }, []);

  if (!links.length) return null;
  return (
    <section className="glass space-y-3 rounded-2xl p-5" aria-labelledby={id}>
      <h3 id={id} className="flex items-center gap-2 font-display text-lg font-semibold text-ink-100">
        <Link2 className="size-5 text-nebula-300" aria-hidden="true" />
        {t("links.title")}
      </h3>
      <ul className="space-y-2.5">
        {links.map((l) => (
          <li key={l.key}>
            <a
              href={l.url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-start gap-1.5 text-sm font-medium text-nebula-300 underline-offset-2 hover:underline"
            >
              {l.label}
              <ExternalLink className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            </a>
            <p className="text-xs text-ink-400">{l.purpose}</p>
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink-400">{t("links.note")}</p>
    </section>
  );
}
