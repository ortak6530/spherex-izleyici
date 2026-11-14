import { motion } from "framer-motion";
import { ExternalLink, Info, Play } from "lucide-react";
import { useTranslation } from "react-i18next";

const IRSA_3I_ATLAS = "https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/index.html";

/** Collection card: the interstellar comet 3I/ATLAS, played frame by frame from IRSA MOST frames. */
function CollectionCard({ onSearch }: { onSearch: (q: string) => void }) {
  const { t } = useTranslation();
  return (
    <article
      className="mt-6 rounded-xl border border-nebula-400/30 bg-space-950/40 p-4"
      aria-labelledby="col-3i-title"
    >
      <p className="font-display text-xs tracking-[0.2em] text-nebula-300 uppercase">
        {t("collection.badge")}
      </p>
      <h2 id="col-3i-title" className="mt-1 font-display text-xl font-semibold text-ink-100">
        {t("collection.atlas.title")}
      </h2>
      <p className="mt-2 text-sm text-ink-300">{t("collection.atlas.body")}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => onSearch("3I/ATLAS")}
          className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg bg-nebula-500 px-4 text-sm font-medium text-white transition-colors duration-200 hover:bg-nebula-600"
        >
          <Play className="size-4" aria-hidden="true" />
          {t("collection.atlas.play")}
        </button>
        <a
          href={IRSA_3I_ATLAS}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-1 text-sm text-nebula-300 underline-offset-2 hover:underline"
        >
          {t("collection.atlas.irsa")}
          <ExternalLink className="size-3.5" aria-hidden="true" />
        </a>
      </div>
    </article>
  );
}

/** Empty-state landing content shown until an object is selected. */
export default function Hero({ onSearch }: { onSearch: (q: string) => void }) {
  const { t } = useTranslation();
  const steps = [t("hero.step1"), t("hero.step2"), t("hero.step3")];
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass w-full max-w-2xl rounded-2xl p-6 sm:p-8"
      aria-labelledby="hero-title"
    >
      <p className="font-display text-sm tracking-[0.2em] text-star-300 uppercase">{t("app.tagline")}</p>
      <h1
        id="hero-title"
        className="mt-2 font-display text-3xl leading-tight font-semibold text-ink-100 sm:text-4xl"
      >
        {t("hero.heading")}
      </h1>
      <p className="mt-4 max-w-prose text-base text-ink-300">{t("hero.body")}</p>
      <ol className="mt-6 grid gap-3 sm:grid-cols-3">
        {steps.map((s, i) => (
          <li key={s} className="rounded-xl border border-white/10 bg-space-950/35 p-3 text-sm text-ink-300">
            <span className="font-mono text-star-300">0{i + 1}</span>
            <p className="mt-1 text-ink-100">{s}</p>
          </li>
        ))}
      </ol>
      <CollectionCard onSearch={onSearch} />
      <p className="mt-6 flex gap-2 text-sm text-ink-400">
        <Info className="mt-0.5 size-4 shrink-0 text-nebula-400" aria-hidden="true" />
        {t("hero.honest")}
      </p>
    </motion.section>
  );
}
