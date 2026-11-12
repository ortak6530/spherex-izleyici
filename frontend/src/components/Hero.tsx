import { motion } from "framer-motion";
import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";

/** Empty-state landing content shown until an object is selected (search is wired in Phase 2). */
export default function Hero() {
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
          <li key={s} className="rounded-xl border border-white/10 bg-space-950/50 p-3 text-sm text-ink-300">
            <span className="font-mono text-star-300">0{i + 1}</span>
            <p className="mt-1 text-ink-100">{s}</p>
          </li>
        ))}
      </ol>
      <p className="mt-6 flex gap-2 text-sm text-ink-400">
        <Info className="mt-0.5 size-4 shrink-0 text-nebula-400" aria-hidden="true" />
        {t("hero.honest")}
      </p>
    </motion.section>
  );
}
