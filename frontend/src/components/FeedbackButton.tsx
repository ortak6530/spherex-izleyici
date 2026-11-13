import { Loader2, MessageSquarePlus, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { apiPost, type Target } from "../lib/api";
import { errorText } from "../lib/format";

const CATEGORIES = ["bug", "idea", "data", "other"] as const;
type Category = (typeof CATEGORIES)[number];
const MAX = 2000;

/** Feedback button + dialog. Stored on the server for the admin panel; page and object are attached. */
export default function FeedbackButton({ target }: { target: Target | null }) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const ids = { msg: useId(), email: useId(), hp: useId() };
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<Category>("idea");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState(""); // honeypot, hidden from people
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    // Fallback to the plain attribute where <dialog> modal support is missing (old browsers, jsdom)
    if (open && !d.open) {
      if (typeof d.showModal === "function") d.showModal();
      else d.setAttribute("open", "");
    }
    if (!open && d.open) {
      if (typeof d.close === "function") d.close();
      else d.removeAttribute("open");
    }
  }, [open]);

  const page = window.location.pathname + window.location.search + window.location.hash;
  const close = () => {
    setOpen(false);
    if (sent) {
      setSent(false);
      setMessage("");
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (message.trim().length < 5) {
      setError(t("feedback.tooShort"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiPost("/feedback", {
        category,
        message: message.trim(),
        email: email.trim() || null,
        page: page.slice(0, 200),
        object_key: target?.key ?? null,
        context: { target_kind: target?.kind ?? null, lang: document.documentElement.lang },
        website: website || null,
      });
      setSent(true);
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("feedback.button")}
        className="flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 px-3 text-sm text-ink-300 transition-colors duration-200 hover:border-white/25 hover:text-ink-100"
      >
        <MessageSquarePlus className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline" aria-hidden="true">
          {t("feedback.button")}
        </span>
      </button>
      <dialog
        ref={ref}
        onClose={close}
        aria-labelledby="fb-title"
        className="glass m-auto w-[min(32rem,calc(100%-2rem))] rounded-2xl p-6 text-ink-300 backdrop:bg-space-950/70"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="fb-title" className="font-display text-xl font-semibold text-ink-100">
            {t("feedback.title")}
          </h2>
          <button
            type="button"
            onClick={close}
            aria-label={t("feedback.close")}
            className="grid size-10 cursor-pointer place-items-center rounded-lg hover:bg-white/10"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
        {sent ? (
          <div className="space-y-4" role="status">
            <p className="text-ink-100">{t("feedback.thanks")}</p>
            <button
              type="button"
              onClick={close}
              className="h-10 cursor-pointer rounded-lg bg-nebula-500 px-4 text-sm font-medium text-white"
            >
              {t("feedback.close")}
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4" noValidate>
            <fieldset>
              <legend className="mb-2 text-sm">{t("feedback.category")}</legend>
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((c) => (
                  <label
                    key={c}
                    className={`cursor-pointer rounded-lg border px-3 py-2 text-sm transition-colors duration-200 ${
                      category === c
                        ? "border-nebula-400 bg-nebula-500/20 text-ink-100"
                        : "border-white/10 hover:text-ink-100"
                    }`}
                  >
                    <input
                      type="radio"
                      name="fb-category"
                      value={c}
                      checked={category === c}
                      onChange={() => setCategory(c)}
                      className="sr-only"
                    />
                    {t(`feedback.categories.${c}`)}
                  </label>
                ))}
              </div>
            </fieldset>
            <div>
              <label htmlFor={ids.msg} className="mb-1 block text-sm">
                {t("feedback.message")}
              </label>
              <textarea
                id={ids.msg}
                value={message}
                maxLength={MAX}
                rows={5}
                required
                onChange={(e) => setMessage(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-space-950/70 p-3 text-sm text-ink-100 focus:border-nebula-400 focus:outline-none"
                aria-describedby={`${ids.msg}-count`}
              />
              <p id={`${ids.msg}-count`} className="text-right font-mono text-xs text-ink-400">
                {message.length}/{MAX}
              </p>
            </div>
            <div>
              <label htmlFor={ids.email} className="mb-1 block text-sm">
                {t("feedback.email")}
              </label>
              <input
                id={ids.email}
                type="email"
                value={email}
                maxLength={254}
                autoComplete="email"
                onChange={(e) => setEmail(e.target.value)}
                className="h-10 w-full rounded-lg border border-white/10 bg-space-950/70 px-3 text-sm text-ink-100 focus:border-nebula-400 focus:outline-none"
                aria-describedby={`${ids.email}-note`}
              />
              <p id={`${ids.email}-note`} className="mt-1 text-xs text-ink-400">
                {t("feedback.emailNote")}
              </p>
            </div>
            {/* Honeypot: invisible to people, bots fill it in and are silently ignored */}
            <div className="hidden" aria-hidden="true">
              <label htmlFor={ids.hp}>Website</label>
              <input
                id={ids.hp}
                tabIndex={-1}
                autoComplete="off"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
              />
            </div>
            <p className="text-xs text-ink-400">
              {t("feedback.context", { page, object: target?.name ?? "—" })}
            </p>
            {error && (
              <p className="text-sm text-danger-400" role="alert">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={busy}
              className="flex h-10 cursor-pointer items-center gap-2 rounded-lg bg-nebula-500 px-4 text-sm font-medium text-white disabled:cursor-wait disabled:opacity-70"
            >
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {t("feedback.send")}
            </button>
          </form>
        )}
      </dialog>
    </>
  );
}
