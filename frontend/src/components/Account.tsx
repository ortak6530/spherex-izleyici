import { Loader2, LogIn, Shield, Trash2, UserRound, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../lib/api";
import { auth, savedHref, useAuth, type SavedItem } from "../lib/auth";
import { syncDialog } from "../lib/dialog";

const input =
  "h-11 w-full rounded-lg border border-white/10 bg-space-950/70 px-3 text-base text-ink-100 focus:border-nebula-400 focus:outline-none";
const primary =
  "flex h-10 cursor-pointer items-center justify-center gap-2 rounded-lg bg-nebula-500 px-4 text-sm font-medium text-white disabled:cursor-wait disabled:opacity-70";

function useErrorText() {
  const { t } = useTranslation();
  return (e: unknown) => {
    if (!(e instanceof ApiError)) return t("errors.generic");
    const b = e.body;
    if (e.code === "INVALID_CODE") return t("account.errors.INVALID_CODE", { n: b.attempts_left ?? 0 });
    if (e.code === "RATE_LIMITED" && b.retry_after_s !== undefined)
      return t("account.errors.RATE_LIMITED_WAIT", {
        min: Math.max(1, Math.ceil(Number(b.retry_after_s) / 60)),
      });
    if (e.code === "EMAIL_RATE_LIMITED")
      return t("account.errors.EMAIL_RATE_LIMITED", { min: Math.ceil(Number(b.retry_after_s ?? 60) / 60) });
    return t(`account.errors.${e.code}`, {
      defaultValue: t(`errors.${e.code}`, { defaultValue: t("errors.generic") }),
    });
  };
}

function Dialog({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => syncDialog(ref.current, open), [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={id}
      className="glass m-auto max-h-[85vh] w-[min(30rem,calc(100%-2rem))] overflow-y-auto rounded-2xl p-6 text-ink-300 backdrop:bg-space-950/70"
    >
      <div className="mb-4 flex items-center justify-between">
        <h2 id={id} className="font-display text-xl font-semibold text-ink-100">
          {title}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("account.close")}
          className="grid size-10 cursor-pointer place-items-center rounded-lg hover:bg-white/10"
        >
          <X className="size-5" aria-hidden="true" />
        </button>
      </div>
      {open && children}
    </dialog>
  );
}

/** Two steps: e-mail -> 6-digit code. The code itself is created and checked on the server. */
export function LoginDialog() {
  const { t } = useTranslation();
  const { loginOpen } = useAuth();
  const errorText = useErrorText();
  const ids = { email: useId(), code: useId() };
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<{ sendsLeft: number; serverLog: boolean } | null>(null);

  const close = () => {
    auth.closeLogin();
    setStep("email");
    setCode("");
    setError(null);
    setInfo(null);
  };

  const sendCode = async (e?: FormEvent) => {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await auth.requestCode(email.trim());
      setInfo({ sendsLeft: r.sends_left, serverLog: r.delivery === "server_log" });
      setStep("code");
      setCode("");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e: FormEvent) => {
    e.preventDefault();
    if (code.length !== 6) {
      setError(t("account.errors.INVALID_CODE_FORMAT"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await auth.verify(email.trim(), code);
      close();
    } catch (err) {
      setError(errorText(err));
      if (err instanceof ApiError && (err.code === "CODE_LOCKED" || err.code === "CODE_EXPIRED")) setCode("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={loginOpen} onClose={close} title={t("account.loginTitle")}>
      {step === "email" ? (
        <form onSubmit={sendCode} className="space-y-4" noValidate>
          <p className="text-sm">{t("account.loginIntro")}</p>
          <div>
            <label htmlFor={ids.email} className="mb-1 block text-sm">
              {t("account.email")}
            </label>
            <input
              id={ids.email}
              type="email"
              autoComplete="email"
              required
              maxLength={254}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={input}
            />
          </div>
          {error && (
            <p className="text-sm text-danger-400" role="alert">
              {error}
            </p>
          )}
          <button type="submit" disabled={busy || !email.trim()} className={primary}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {t("account.sendCode")}
          </button>
          <p className="text-xs text-ink-400">{t("account.privacy")}</p>
        </form>
      ) : (
        <form onSubmit={verify} className="space-y-4" noValidate>
          <p className="text-sm" role="status">
            {t("account.codeSent", { email: email.trim() })}
          </p>
          {info?.serverLog && <p className="text-xs text-warn-400">{t("account.devServerLog")}</p>}
          <div>
            <label htmlFor={ids.code} className="mb-1 block text-sm">
              {t("account.code")}
            </label>
            <input
              id={ids.code}
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              className={`${input} text-center font-mono text-2xl tracking-[0.5em]`}
            />
          </div>
          {error && (
            <p className="text-sm text-danger-400" role="alert">
              {error}
            </p>
          )}
          <button type="submit" disabled={busy} className={primary}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {t("account.verify")}
          </button>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <button
              type="button"
              onClick={() => {
                setStep("email");
                setError(null);
              }}
              className="cursor-pointer text-nebula-300 hover:underline"
            >
              {t("account.changeEmail")}
            </button>
            <button
              type="button"
              disabled={busy || (info?.sendsLeft ?? 0) <= 0}
              onClick={() => void sendCode()}
              className="cursor-pointer text-nebula-300 hover:underline disabled:cursor-not-allowed disabled:text-ink-400 disabled:no-underline"
            >
              {t("account.resend", { n: info?.sendsLeft ?? 0 })}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

function SavedList({ items, title, empty }: { items: SavedItem[]; title: string; empty: string }) {
  const { t } = useTranslation();
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-ink-100">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-ink-400">{empty}</p>
      ) : (
        <ul className="space-y-1">
          {items.map((s) => (
            <li
              key={s.id}
              className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-white/5"
            >
              <a href={savedHref(s)} className="min-w-0 truncate text-sm text-nebula-300 hover:underline">
                {s.label}
              </a>
              <button
                type="button"
                onClick={() => void auth.remove(s.id)}
                aria-label={t("account.remove", { label: s.label })}
                className="grid size-8 shrink-0 cursor-pointer place-items-center rounded-lg text-ink-400 hover:bg-white/10 hover:text-ink-100"
              >
                <Trash2 className="size-4" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Top-bar button: "Giriş" when signed out, the account dialog (lists, sign-out) when signed in. */
export default function AccountButton() {
  const { t } = useTranslation();
  const { ready, user, saved } = useAuth();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    void auth.load();
  }, []);

  const btn =
    "flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 px-3 text-sm text-ink-300 transition-colors duration-200 hover:border-white/25 hover:text-ink-100";
  if (!ready) return null;
  return (
    <>
      {user ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className={btn}
          aria-label={t("account.myAccount")}
        >
          <UserRound className="size-4" aria-hidden="true" />
          <span className="hidden max-w-[10rem] truncate sm:inline" aria-hidden="true">
            {user.email}
          </span>
        </button>
      ) : (
        <button type="button" onClick={auth.openLogin} className={btn} aria-label={t("account.login")}>
          <LogIn className="size-4" aria-hidden="true" />
          <span className="hidden sm:inline" aria-hidden="true">
            {t("account.login")}
          </span>
        </button>
      )}
      <LoginDialog />
      <Dialog open={open && !!user} onClose={() => setOpen(false)} title={t("account.myAccount")}>
        {user && (
          <div className="space-y-5">
            <p className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-ink-100">{user.email}</span>
              {user.is_admin && (
                <span className="inline-flex items-center gap-1 rounded-full border border-star-400/40 px-2 py-0.5 text-xs text-star-300">
                  <Shield className="size-3" aria-hidden="true" /> {t("account.admin")}
                </span>
              )}
            </p>
            <SavedList
              items={saved.filter((s) => s.kind === "object")}
              title={t("account.objects")}
              empty={t("account.noObjects")}
            />
            <SavedList
              items={saved.filter((s) => s.kind === "comparison")}
              title={t("account.studies")}
              empty={t("account.noStudies")}
            />
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                void auth.logout();
              }}
              className="h-10 cursor-pointer rounded-lg border border-white/10 px-4 text-sm text-ink-100 hover:bg-white/5"
            >
              {t("account.logout")}
            </button>
          </div>
        )}
      </Dialog>
    </>
  );
}
