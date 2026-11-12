import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiGet, type Attribution } from "../lib/api";

export default function AttributionsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const [items, setItems] = useState<Attribution[] | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
    if (open && items === null) {
      apiGet<{ items: Attribution[] }>("/meta/attributions")
        .then((r) => setItems(r.items))
        .catch(() => setItems([]));
    }
  }, [open, items]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="attr-title"
      className="glass m-auto max-h-[85vh] w-[min(46rem,calc(100%-2rem))] overflow-y-auto rounded-2xl p-6 text-ink-300 backdrop:bg-space-950/70"
    >
      <div className="mb-4 flex items-center justify-between">
        <h2 id="attr-title" className="font-display text-xl font-semibold text-ink-100">
          {t("attributions.title")}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("attributions.close")}
          className="grid size-10 cursor-pointer place-items-center rounded-lg hover:bg-white/10"
        >
          <X className="size-5" aria-hidden="true" />
        </button>
      </div>
      <ul className="space-y-4 text-sm">
        {(items ?? []).map((a) => (
          <li key={a.key}>
            <h3 className="font-semibold text-ink-100">{a.title}</h3>
            <p className="mt-1">{a.text}</p>
            {a.dois && <p className="mt-1 font-mono text-xs text-ink-400">DOI: {a.dois.join(" · ")}</p>}
            {a.url && (
              <a
                href={a.url}
                target="_blank"
                rel="noreferrer noopener"
                className="text-nebula-300 hover:underline"
              >
                {a.url}
              </a>
            )}
          </li>
        ))}
      </ul>
    </dialog>
  );
}
