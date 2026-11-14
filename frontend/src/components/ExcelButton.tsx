import { FileSpreadsheet, Loader2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { apiPost } from "../lib/api";
import { errorText } from "../lib/format";
import { runJob, type ProgressStep } from "../lib/jobs";

export type ExportItem = { q: string; d?: number };
type ExportResult = { file_id: string; filename: string; size_bytes: number; rows: Record<string, number> };

/** The server builds the .xlsx (openpyxl) as a job; the file is then fetched by this same browser. */
async function downloadXlsx(
  items: ExportItem[],
  filters: Record<string, unknown> | undefined,
  onProgress?: (s: ProgressStep) => void,
) {
  const body = filters && Object.keys(filters).length ? { items, filters } : { items };
  const r = await runJob<ExportResult>(() => apiPost("/export/xlsx", body), onProgress);
  const a = document.createElement("a");
  a.href = `/api/v1/export/${encodeURIComponent(r.file_id)}`;
  a.download = r.filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  return r;
}

export default function ExcelButton({
  items,
  label,
  filters,
}: {
  items: ExportItem[];
  label?: string;
  filters?: Record<string, unknown>; // the page's observation filters (date / release / λ)
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const click = async () => {
    setBusy(true);
    setError(null);
    try {
      await downloadXlsx(items, filters, (s) =>
        setStep(
          t(`export.progress.${s.step}`, {
            ...s,
            defaultValue: t(`workspace.progress.${s.step}`, { ...s, defaultValue: "" }),
          }),
        ),
      );
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
      setStep(null);
    }
  };

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => void click()}
        disabled={busy || items.length === 0}
        className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 px-3 text-sm text-ink-300 transition-colors duration-200 hover:border-white/25 hover:text-ink-100 disabled:cursor-wait disabled:opacity-70"
      >
        {busy ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <FileSpreadsheet className="size-4" aria-hidden="true" />
        )}
        {label ?? t("export.button")}
      </button>
      {busy && step && (
        <span className="text-xs text-ink-400" role="status">
          {step}
        </span>
      )}
      {error && (
        <span className="text-xs text-danger-400" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
