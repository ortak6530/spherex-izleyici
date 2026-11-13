import { AlertTriangle, GitCompareArrows, Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import CutoutView, { type DecodedCutout } from "../components/CutoutView";
import ProgressLine from "../components/ProgressLine";
import SaveButton from "../components/SaveButton";
import { apiGet, apiPost, type ResolveResponse, type Target } from "../lib/api";
import { errorText, fmt, warningText, type Warning } from "../lib/format";
import { runJob, runMaybeJob } from "../lib/jobs";
import { decodeFloat32, type Colormap, type Stretch } from "../render/image";
import { ViewControls } from "./CompareView";

interface ObjView {
  image_id: string;
  release: string;
  obs_id: string;
  detector: number;
  date_obs: string;
  fits_url: string;
  wavelength_um: number;
  bandwidth_um: number;
  pipeline_version: string | null;
  target_px: [number, number];
  pixel_scale_arcsec: number;
  orientation: { north_deg: number; east_deg: number; pixel_scale_arcsec: number };
  photometry: { flux_ujy: number; err_ujy: number } | null;
  ab_mag: number | null;
  own_limits: [number, number];
  width: number;
  height: number;
  data_b64: string;
}

interface Facts {
  name: string;
  main_id: string | null;
  otype: string | null;
  otype_desc: string | null;
  sp_type: string | null;
  distance: { pc: number; source: string } | null;
  mags: Record<string, number | null>;
  pmra_mas_yr: number | null;
  pmdec_mas_yr: number | null;
  source: string | null;
}

interface ObjectCompareResult {
  id: string;
  channel: { delta_um: number; ratio: number; status: string };
  objects: { a: Facts; b: Facts };
  same_type: boolean;
  warnings: Warning[];
  a_view: ObjView;
  b_view: ObjView;
  shared_limits: [number, number];
  flux_ratio_b_over_a: number | null;
}

interface Suggestion {
  label: string;
  main_id: string;
  otype: string;
}

const toDecoded = (v: ObjView): DecodedCutout => ({
  raw: {
    width: v.width,
    height: v.height,
    meta: {
      unit: "MJy/sr",
      target_px: v.target_px,
      wavelength_um: v.wavelength_um,
      date_obs: v.date_obs,
      north_deg: v.orientation.north_deg,
      east_deg: v.orientation.east_deg,
      pixel_scale_arcsec: v.orientation.pixel_scale_arcsec,
    },
  },
  data: decodeFloat32(v.data_b64),
  lambda: null,
});

export default function ObjectCompare({
  target,
  imageA,
  size,
  zodi,
}: {
  target: Target;
  imageA: string | null;
  size: number;
  zodi: boolean;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [second, setSecond] = useState<Target | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<string | null>(null);
  const [result, setResult] = useState<ObjectCompareResult | null>(null);
  const [shared, setShared] = useState(true);
  const [stretch, setStretch] = useState<Stretch>("asinh");
  const [cmap, setCmap] = useState<Colormap>("inferno");

  // Same-type suggestions (SIMBAD otype), most studied first
  useEffect(() => {
    if (!target.main_id || !target.otype) return;
    const ctrl = new AbortController();
    const path = `/objects/similar?main_id=${encodeURIComponent(target.main_id)}&otype=${encodeURIComponent(target.otype)}`;
    runMaybeJob<{ items: Suggestion[] }>(() => apiGet(path, ctrl.signal), undefined, ctrl.signal)
      .then((r) => setSuggestions(r.items))
      .catch(() => setSuggestions([]));
    return () => ctrl.abort();
  }, [target.main_id, target.otype]);

  const resolveSecond = async (q: string) => {
    setMessage(null);
    try {
      const r = await apiGet<ResolveResponse>(`/resolve?q=${encodeURIComponent(q)}`);
      if (r.target && r.target.ra !== undefined) {
        setSecond(r.target);
        setQuery(r.target.name);
      } else {
        setMessage(t("search.noResult"));
      }
    } catch (e) {
      setMessage(errorText(t, e));
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) void resolveSecond(query.trim());
  };

  const run = async () => {
    if (!second || !imageA) return;
    setBusy(true);
    setMessage(null);
    setResult(null);
    const ref = (x: Target) => ({
      name: x.name,
      main_id: x.main_id ?? null,
      key: x.key,
      ra: x.ra,
      dec: x.dec,
    });
    try {
      const r = await runJob<ObjectCompareResult>(
        () =>
          apiPost("/compare/objects", {
            a: ref(target),
            b: ref(second),
            image_a: imageA,
            size_deg: size,
            zodi: zodi ? "sub" : "raw",
          }),
        (s) => setStep(t(`workspace.progress.${s.step}`, { ...s, defaultValue: s.step })),
      );
      setResult(r);
    } catch (e) {
      setMessage(errorText(t, e));
    } finally {
      setBusy(false);
      setStep(null);
    }
  };

  const views = useMemo(
    () => (result ? { a: toDecoded(result.a_view), b: toDecoded(result.b_view) } : null),
    [result],
  );
  const typeMismatch = second?.otype && target.otype && second.otype !== target.otype;

  const row = (label: string, fa: React.ReactNode, fb: React.ReactNode) => (
    <tr className="border-b border-white/5">
      <th scope="row" className="py-1.5 pr-3 text-left font-normal text-ink-400">
        {label}
      </th>
      <td className="py-1.5 pr-3 text-ink-100">{fa}</td>
      <td className="py-1.5 text-ink-100">{fb}</td>
    </tr>
  );
  const unknown = t("info.unknown");
  const mags = (m: Record<string, number | null>) =>
    Object.keys(m).length
      ? Object.entries(m)
          .map(([k, v]) => `${k} ${fmt(v, 2)}`)
          .join(" · ")
      : unknown;
  const flux = (v: ObjView) =>
    v.photometry
      ? `${fmt(v.photometry.flux_ujy, 1)} ± ${fmt(v.photometry.err_ujy, 1)} µJy @ ${v.wavelength_um.toFixed(3)} µm`
      : t("result.noBrightness");

  return (
    <section className="glass space-y-4 rounded-2xl p-5" aria-labelledby="objcmp-title">
      <div>
        <h3 id="objcmp-title" className="font-display text-lg font-semibold text-ink-100">
          {t("objcmp.title")}
        </h3>
        <p className="text-sm text-ink-300">{t("objcmp.intro")}</p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
        <label className="min-w-64 flex-1 text-xs text-ink-400">
          {t("objcmp.second")}
          <div className="relative">
            <Search
              className="pointer-events-none absolute top-2.5 left-3 size-5 text-ink-400"
              aria-hidden="true"
            />
            <input
              value={query}
              maxLength={100}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("objcmp.placeholder")}
              className="h-10 w-full rounded-lg border border-white/10 bg-space-950/70 pl-10 text-sm text-ink-100 placeholder:text-ink-400 focus:border-nebula-400 focus:outline-none"
            />
          </div>
        </label>
        <button
          type="submit"
          className="h-10 cursor-pointer rounded-lg border border-white/15 px-4 text-sm text-ink-100 hover:border-white/30"
        >
          {t("objcmp.pick")}
        </button>
      </form>

      {suggestions.length > 0 && (
        <div>
          <p className="mb-1 text-xs text-ink-400">{t("objcmp.sameType", { type: target.otype })}</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s.main_id}
                type="button"
                onClick={() => void resolveSecond(s.main_id)}
                className="h-8 cursor-pointer rounded-full border border-ok-400/30 bg-ok-400/10 px-3 text-xs text-ok-400 hover:bg-ok-400/20"
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {second && (
        <p className="text-sm text-ink-300">
          {t("objcmp.selected", { name: second.name })} · {second.otype ?? ""}
        </p>
      )}
      {typeMismatch && (
        <p className="flex items-start gap-2 text-sm text-warn-400">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {t("objcmp.otherType", { a: target.otype, b: second?.otype })}
        </p>
      )}
      {!imageA && <p className="text-sm text-ink-400">{t("objcmp.needA")}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={!second || !imageA || busy}
          onClick={() => void run()}
          className="flex h-10 cursor-pointer items-center gap-2 rounded-lg bg-star-400 px-4 text-sm font-semibold text-space-950 hover:bg-star-300 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? <Loader2 className="size-4 animate-spin" /> : <GitCompareArrows className="size-4" />}
          {t("objcmp.run")}
        </button>
        {step && <ProgressLine text={step} />}
      </div>
      {message && (
        <p role="alert" className="text-sm text-danger-400">
          {message}
        </p>
      )}

      {result && views && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div role="radiogroup" className="flex gap-2">
              {[true, false].map((v) => (
                <button
                  key={String(v)}
                  role="radio"
                  aria-checked={shared === v}
                  onClick={() => setShared(v)}
                  className={`h-9 cursor-pointer rounded-lg px-3 text-sm ${
                    shared === v ? "bg-nebula-500 text-white" : "border border-white/10 text-ink-300"
                  }`}
                >
                  {v ? t("objcmp.scaleShared") : t("objcmp.scaleOwn")}
                </button>
              ))}
            </div>
            <ViewControls stretch={stretch} setStretch={setStretch} cmap={cmap} setCmap={setCmap} />
            <SaveButton
              kind="comparison"
              refId={result.id}
              label={`${result.objects.a.name} ↔ ${result.objects.b.name}`}
              data={{ q: target.name }}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {(["a", "b"] as const).map((k) => {
              const v = result[`${k}_view`];
              return (
                <CutoutView
                  key={k}
                  cutout={views[k]}
                  limits={shared ? result.shared_limits : v.own_limits}
                  stretch={stretch}
                  cmap={cmap}
                  label={`${result.objects[k].name} · λ ${v.wavelength_um.toFixed(3)} µm · ${v.date_obs.slice(0, 10)}`}
                />
              );
            })}
          </div>
          <p className={`text-xs ${shared ? "text-ink-400" : "text-warn-400"}`}>
            {shared ? t("objcmp.scaleNoteShared") : t("objcmp.scaleNoteOwn")} ·{" "}
            {t("workspace.deltaLambda", {
              dl: (result.channel.delta_um * 1000).toFixed(1),
              ratio: result.channel.ratio.toFixed(2),
            })}
          </p>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[32rem] text-sm">
              <caption className="mb-2 text-left font-semibold text-ink-100">{t("objcmp.table")}</caption>
              <thead>
                <tr className="border-b border-white/10 text-left text-ink-300">
                  <th scope="col" className="py-1.5 pr-3 font-normal">
                    {t("objcmp.property")}
                  </th>
                  <th scope="col" className="py-1.5 pr-3">
                    {result.objects.a.name}
                  </th>
                  <th scope="col" className="py-1.5">
                    {result.objects.b.name}
                  </th>
                </tr>
              </thead>
              <tbody>
                {row(
                  t("objcmp.type"),
                  result.objects.a.otype_desc ?? result.objects.a.otype ?? unknown,
                  result.objects.b.otype_desc ?? result.objects.b.otype ?? unknown,
                )}
                {row(
                  t("objcmp.spType"),
                  result.objects.a.sp_type ?? unknown,
                  result.objects.b.sp_type ?? unknown,
                )}
                {row(
                  t("objcmp.distance"),
                  result.objects.a.distance ? `${fmt(result.objects.a.distance.pc, 2)} pc` : unknown,
                  result.objects.b.distance ? `${fmt(result.objects.b.distance.pc, 2)} pc` : unknown,
                )}
                {row(t("objcmp.mags"), mags(result.objects.a.mags), mags(result.objects.b.mags))}
                {row(
                  t("objcmp.pm"),
                  result.objects.a.pmra_mas_yr != null
                    ? `${fmt(result.objects.a.pmra_mas_yr, 1)} / ${fmt(result.objects.a.pmdec_mas_yr, 1)}`
                    : unknown,
                  result.objects.b.pmra_mas_yr != null
                    ? `${fmt(result.objects.b.pmra_mas_yr, 1)} / ${fmt(result.objects.b.pmdec_mas_yr, 1)}`
                    : unknown,
                )}
                {row(t("objcmp.spherexFlux"), flux(result.a_view), flux(result.b_view))}
                {row(t("objcmp.spherexAb"), fmt(result.a_view.ab_mag, 2), fmt(result.b_view.ab_mag, 2))}
                {row(
                  t("objcmp.date"),
                  `${result.a_view.date_obs.slice(0, 10)} · ${result.a_view.release.toUpperCase()}`,
                  `${result.b_view.date_obs.slice(0, 10)} · ${result.b_view.release.toUpperCase()}`,
                )}
              </tbody>
            </table>
          </div>
          {result.flux_ratio_b_over_a !== null && (
            <p className="text-sm text-ink-300">
              {t("objcmp.ratio", { r: fmt(result.flux_ratio_b_over_a, 2) })}
            </p>
          )}
          <p className="text-xs text-ink-400">{t("objcmp.source")}</p>

          {result.warnings.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm text-warn-400">
              {result.warnings.map((w, i) => (
                <li key={`${w.code}-${i}`}>{warningText(t, w)}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
