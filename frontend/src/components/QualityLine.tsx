import { ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

/** "Veri kalitesi" line under an image: masked-pixel share and every correction that was applied. */
export default function QualityLine({ items }: { items: string[] }) {
  const { t } = useTranslation();
  if (!items.length) return null;
  return (
    <p className="flex flex-wrap items-start gap-x-2 gap-y-0.5 text-xs text-ink-300">
      <span className="inline-flex items-center gap-1 font-medium text-ink-100">
        <ShieldCheck className="size-3.5 text-ok-400" aria-hidden="true" />
        {t("quality.title")}:
      </span>
      {items.map((s, i) => (
        <span key={s}>
          {s}
          {i < items.length - 1 ? " ·" : ""}
        </span>
      ))}
    </p>
  );
}
