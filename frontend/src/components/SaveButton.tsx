import { Bookmark, BookmarkCheck, Loader2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { auth, useAuth, type SavedItem } from "../lib/auth";

/** Adds an object to the user's list or saves a study; signed-out visitors get the sign-in dialog. */
export default function SaveButton({
  kind,
  refId,
  label,
  data,
}: {
  kind: SavedItem["kind"];
  refId: string;
  label: string;
  data?: SavedItem["data"];
}) {
  const { t } = useTranslation();
  const { user, saved } = useAuth();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const existing = saved.find((s) => s.kind === kind && s.ref === refId);
  const text = existing
    ? t(kind === "object" ? "account.inList" : "account.studySaved")
    : t(kind === "object" ? "account.addToList" : "account.saveStudy");

  const click = async () => {
    if (!user) return auth.openLogin();
    setBusy(true);
    setFailed(false);
    try {
      if (existing) await auth.remove(existing.id);
      else await auth.save(kind, refId, label, data);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => void click()}
        disabled={busy}
        aria-pressed={!!existing}
        title={user ? undefined : t("account.loginToSave")}
        className={`inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border px-3 text-sm transition-colors duration-200 disabled:cursor-wait ${
          existing
            ? "border-nebula-400/60 bg-nebula-500/15 text-ink-100"
            : "border-white/10 text-ink-300 hover:border-white/25 hover:text-ink-100"
        }`}
      >
        {busy ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : existing ? (
          <BookmarkCheck className="size-4" aria-hidden="true" />
        ) : (
          <Bookmark className="size-4" aria-hidden="true" />
        )}
        {text}
      </button>
      {failed && (
        <span className="text-xs text-danger-400" role="alert">
          {t("account.saveFailed")}
        </span>
      )}
    </span>
  );
}
