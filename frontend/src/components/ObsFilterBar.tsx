import { Filter, X } from "lucide-react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { isActive, NO_FILTERS, type ObsFilters } from "../lib/obsFilters";

/** Date / release / λ filters above the visit lists (one row; wraps on phones). */
export default function ObsFilterBar({
  value,
  onChange,
  releases,
  shown,
  total,
}: {
  value: ObsFilters;
  onChange: (f: ObsFilters) => void;
  releases: { id: string; label: string }[];
  shown: number;
  total: number;
}) {
  const { t } = useTranslation();
  const id = useId();
  const input =
    "h-9 rounded-lg border border-white/10 bg-space-950/70 px-2 text-sm text-ink-100 focus:border-nebula-400 focus:outline-none";
  const set = (patch: Partial<ObsFilters>) => onChange({ ...value, ...patch });
  const toggle = (rid: string) =>
    set({
      releases: value.releases.includes(rid)
        ? value.releases.filter((r) => r !== rid)
        : [...value.releases, rid],
    });

  return (
    <fieldset className="space-y-2 rounded-xl border border-white/10 p-3">
      <legend className="flex items-center gap-1.5 px-1 text-sm text-ink-300">
        <Filter className="size-4" aria-hidden="true" />
        {t("filters.title")}
      </legend>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-ink-400" htmlFor={`${id}-from`}>
          {t("filters.from")}
          <input
            id={`${id}-from`}
            type="date"
            value={value.from}
            onChange={(e) => set({ from: e.target.value })}
            className={`${input} block`}
          />
        </label>
        <label className="text-xs text-ink-400" htmlFor={`${id}-to`}>
          {t("filters.to")}
          <input
            id={`${id}-to`}
            type="date"
            value={value.to}
            onChange={(e) => set({ to: e.target.value })}
            className={`${input} block`}
          />
        </label>
        <div className="text-xs text-ink-400">
          {t("filters.releases")}
          <div className="flex h-9 items-center gap-3">
            {releases.map((r) => (
              <label
                key={r.id}
                className="inline-flex cursor-pointer items-center gap-1.5 text-sm text-ink-100"
              >
                <input
                  type="checkbox"
                  checked={value.releases.length === 0 || value.releases.includes(r.id)}
                  onChange={() =>
                    // "all" is stored as []: the first click narrows to the others
                    value.releases.length === 0
                      ? set({ releases: releases.map((x) => x.id).filter((x) => x !== r.id) })
                      : toggle(r.id)
                  }
                  className="size-4 accent-nebula-500"
                />
                {r.label}
              </label>
            ))}
          </div>
        </div>
        <label className="text-xs text-ink-400" htmlFor={`${id}-lmin`}>
          {t("filters.lamMin")}
          <input
            id={`${id}-lmin`}
            inputMode="decimal"
            value={value.lamMin}
            onChange={(e) => set({ lamMin: e.target.value })}
            placeholder="0.75"
            className={`${input} block w-24`}
          />
        </label>
        <label className="text-xs text-ink-400" htmlFor={`${id}-lmax`}>
          {t("filters.lamMax")}
          <input
            id={`${id}-lmax`}
            inputMode="decimal"
            value={value.lamMax}
            onChange={(e) => set({ lamMax: e.target.value })}
            placeholder="5.0"
            className={`${input} block w-24`}
          />
        </label>
        {isActive(value) && (
          <button
            type="button"
            onClick={() => onChange(NO_FILTERS)}
            className="inline-flex h-9 cursor-pointer items-center gap-1 rounded-lg px-2 text-sm text-nebula-300 hover:bg-white/5"
          >
            <X className="size-4" aria-hidden="true" />
            {t("filters.clear")}
          </button>
        )}
      </div>
      <p className="text-xs text-ink-400" role="status">
        {isActive(value) ? t("filters.shown", { shown, total }) : t("filters.none", { total })} ·{" "}
        {t("filters.excelNote")}
      </p>
    </fieldset>
  );
}
