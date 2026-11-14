import { Info, Languages, LogIn, UserRound } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { setLang } from "../i18n";
import { auth, useAuth } from "../lib/auth";
import { entryChoice, hasDeepLink } from "../lib/entry";
import { track } from "../lib/events";
import { LoginDialog } from "./Account";

function WelcomeScreen({ onGuest }: { onGuest: () => void }) {
  const { t, i18n } = useTranslation();
  const btn =
    "inline-flex h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-xl px-5 text-base font-medium transition-colors duration-200 sm:w-auto";
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <section
        aria-labelledby="welcome-title"
        className="glass w-full max-w-xl rounded-2xl p-6 text-center sm:p-10"
      >
        <img src="/favicon.svg" alt="" className="mx-auto size-16" />
        <h1
          id="welcome-title"
          className="mt-4 font-display text-3xl font-semibold tracking-wide text-ink-100 sm:text-4xl"
        >
          {t("app.title")}
        </h1>
        <p className="mt-3 text-base text-ink-300">{t("welcome.lead")}</p>
        <div className="mt-8 flex flex-col items-stretch justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={auth.openLogin}
            className={`${btn} bg-nebula-500 text-white hover:bg-nebula-600`}
          >
            <LogIn className="size-5" aria-hidden="true" />
            {t("welcome.login")}
          </button>
          <button
            type="button"
            onClick={onGuest}
            className={`${btn} border border-white/15 text-ink-100 hover:border-white/30 hover:bg-white/5`}
          >
            <UserRound className="size-5" aria-hidden="true" />
            {t("welcome.guest")}
          </button>
        </div>
        <div className="mt-8 space-y-1.5 rounded-xl border border-white/10 bg-space-950/50 p-4 text-left text-sm text-ink-300">
          <p className="flex items-start gap-2">
            <Info className="mt-0.5 size-4 shrink-0 text-nebula-300" aria-hidden="true" />
            <span>{t("welcome.privacyLogin")}</span>
          </p>
          <p className="pl-6">{t("welcome.privacyGuest")}</p>
        </div>
        <button
          type="button"
          onClick={() => setLang(i18n.language === "tr" ? "en" : "tr")}
          className="mt-6 inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 px-3 text-sm text-ink-300 hover:border-white/25 hover:text-ink-100"
        >
          <Languages className="size-4" aria-hidden="true" />
          {t("lang.switch")}
        </button>
      </section>
      <LoginDialog />
    </main>
  );
}

/**
 * First screen in front of the existing site: sign in or continue as a guest.
 * Skipped when the visitor is signed in, already chose in this session, opened a deep link,
 * or a full page (#admin, #kaynaklar) is open (`bypass`). Signing out shows it again.
 */
export default function EntryGate({ bypass = false, children }: { bypass?: boolean; children: ReactNode }) {
  const { ready, user } = useAuth();
  const [entered, setEntered] = useState(() => entryChoice.get() || hasDeepLink());
  const prevUser = useRef(user);

  useEffect(() => {
    if (hasDeepLink()) entryChoice.set(); // going "home" later does not interrupt with the screen
    // The top bar (which normally loads the account) is not mounted behind this screen
    if (!entered && !auth.get().ready) void auth.load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on load
  }, []);

  useEffect(() => {
    if (prevUser.current && !user) {
      entryChoice.clear(); // signed out -> back to the welcome screen
      setEntered(false);
    }
    prevUser.current = user;
  }, [user]);

  if (bypass || entered || user) return <>{children}</>;
  if (!ready) return <main className="flex-1" aria-busy="true" />; // signed in? known in a moment
  return (
    <WelcomeScreen
      onGuest={() => {
        entryChoice.set();
        setEntered(true);
        track("ui_action", { payload: { button: "continue_as_guest" } });
      }}
    />
  );
}
