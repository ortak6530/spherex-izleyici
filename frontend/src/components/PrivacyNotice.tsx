import { ShieldCheck } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getConsent, setConsent } from "../lib/events";

/** First-visit privacy notice (KVKK): explains what is logged and lets the visitor opt out. */
export default function PrivacyNotice({ forceOpen, onClose }: { forceOpen?: boolean; onClose?: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(() => getConsent() === null);
  const [details, setDetails] = useState(false);
  const visible = open || !!forceOpen;

  const choose = (c: "all" | "essential") => {
    setConsent(c);
    setOpen(false);
    onClose?.();
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.section
          role="dialog"
          aria-labelledby="privacy-title"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 24 }}
          transition={{ duration: 0.25 }}
          className="glass fixed right-3 bottom-3 left-3 z-50 max-w-xl rounded-2xl p-5 sm:left-auto"
        >
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 size-6 shrink-0 text-ok-400" aria-hidden="true" />
            <div className="space-y-2 text-sm text-ink-300">
              <h2 id="privacy-title" className="font-display text-base font-semibold text-ink-100">
                {t("privacy.title")}
              </h2>
              <p>{t("privacy.summary")}</p>
              {details && <p>{t("privacy.details")}</p>}
              <p className="text-ink-400">{t("privacy.essentialNote")}</p>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => choose("all")}
                  className="h-10 cursor-pointer rounded-lg bg-star-400 px-4 font-semibold text-space-950 transition-colors duration-200 hover:bg-star-300"
                >
                  {t("privacy.acceptAll")}
                </button>
                <button
                  type="button"
                  onClick={() => choose("essential")}
                  className="h-10 cursor-pointer rounded-lg border border-white/15 px-4 text-ink-100 transition-colors duration-200 hover:border-white/30"
                >
                  {t("privacy.essentialOnly")}
                </button>
                <button
                  type="button"
                  onClick={() => setDetails((d) => !d)}
                  aria-expanded={details}
                  className="h-10 cursor-pointer px-2 text-nebula-300 underline-offset-4 hover:underline"
                >
                  {details ? t("privacy.less") : t("privacy.more")}
                </button>
              </div>
            </div>
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}
