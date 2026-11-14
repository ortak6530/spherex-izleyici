import { ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiGet, apiPost } from "../lib/api";
import { auth, useAuth } from "../lib/auth";
import { errorText } from "../lib/format";
import { realtime, type WsStatus } from "../lib/realtime";

type Tab = "summary" | "live" | "users" | "feedback" | "releases";
const TABS: Tab[] = ["summary", "live", "users", "feedback", "releases"];
const GROUPS = ["", "search", "compare", "download", "account", "feedback"] as const;
const MAX_FEED = 200;
const POLL_MS = 15_000;

interface Summary {
  users: number;
  events_24h: number;
  events_24h_by_type: Record<string, number>;
  sessions_24h: number;
  feedback_new: number;
  email_mode: string;
  note: string;
}
interface AdminUser {
  id: number;
  email: string;
  is_admin: boolean;
  created_at: string | null;
  last_login_at: string | null;
  saved: number;
  events: number;
}
interface FeedEvent {
  id?: number;
  ts: string | null;
  type: string;
  object_key?: string | null;
  page?: string | null;
  payload?: Record<string, unknown> | null;
  user?: string | null;
  session?: string;
  live?: boolean;
}
interface FeedbackRow {
  id: number;
  created_at: string | null;
  category: string;
  message: string;
  email: string | null;
  page: string | null;
  object_key: string | null;
  status: "new" | "read" | "done";
}
interface ReleaseRow {
  id: string;
  label: string;
  status: string;
  announced: boolean;
  calib_family: string;
  doi: string | null;
  cache: { files: number; bytes: number; newest: number | null };
}
interface ReleasesInfo {
  default: string;
  releases: ReleaseRow[];
  cache: Record<string, { files: number; bytes: number; newest: number | null }>;
  config_file: string;
}

const when = (iso: string | null | undefined) =>
  iso ? new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleString("tr-TR") : "—";
const mb = (b: number) => (b / 1024 / 1024).toFixed(1) + " MB";
const card = "rounded-xl border border-white/10 bg-space-950/35 p-4";
const th = "px-2 py-1.5 text-left text-xs font-medium text-ink-400";
const td = "px-2 py-1.5 align-top text-sm text-ink-100";

function SummaryTab() {
  const { t } = useTranslation();
  const [s, setS] = useState<Summary | null>(null);
  useEffect(() => {
    apiGet<Summary>("/admin/summary").then(setS, () => setS(null));
  }, []);
  if (!s) return <Loader2 className="size-5 animate-spin text-nebula-300" aria-label={t("admin.loading")} />;
  const stats: Array<[string, number | string]> = [
    [t("admin.users"), s.users],
    [t("admin.events24h"), s.events_24h],
    [t("admin.sessions24h"), s.sessions_24h],
    [t("admin.feedbackNew"), s.feedback_new],
    [t("admin.emailMode"), s.email_mode],
  ];
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {stats.map(([k, v]) => (
          <div key={k} className={card}>
            <p className="text-xs text-ink-400">{k}</p>
            <p className="mt-1 font-mono text-xl text-ink-100">{v}</p>
          </div>
        ))}
      </div>
      <div className={card}>
        <p className="mb-2 text-sm text-ink-300">{t("admin.byType")}</p>
        <ul className="grid gap-1 font-mono text-sm sm:grid-cols-3">
          {Object.entries(s.events_24h_by_type)
            .sort((a, b) => b[1] - a[1])
            .map(([k, v]) => (
              <li key={k} className="flex justify-between gap-3">
                <span className="text-ink-300">{k}</span>
                <span className="text-ink-100">{v}</span>
              </li>
            ))}
        </ul>
      </div>
      <p className="text-xs text-ink-400">{s.note}</p>
    </div>
  );
}

function LiveTab() {
  const { t } = useTranslation();
  const [group, setGroup] = useState<(typeof GROUPS)[number]>("");
  const [items, setItems] = useState<FeedEvent[]>([]);
  const [ws, setWs] = useState<WsStatus>("closed");
  const [live, setLive] = useState<"ok" | "forbidden" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiGet<{ items: FeedEvent[] }>(`/admin/events?limit=100${group ? `&group=${group}` : ""}`).then(
      (r) => {
        setItems(r.items);
        setError(null);
      },
      (e: unknown) => setError(errorText(t, e)),
    );
  }, [group, t]);

  useEffect(load, [load]);
  useEffect(() => realtime.onStatus(setWs), []);
  useEffect(() => {
    const off = realtime.onMessage((m) => {
      if (m.type === "subscribed" && m.topic === "admin") setLive("ok");
      if (m.type === "error" && m.topic === "admin") setLive("forbidden");
      if (m.type !== "admin_event") return;
      const ev: FeedEvent = {
        ts: m.ts as string,
        type: m.kind === "feedback" ? "feedback" : String(m.event_type ?? "?"),
        object_key: (m.object_key as string | null) ?? null,
        page: (m.page as string | null) ?? null,
        payload:
          m.kind === "feedback"
            ? { category: m.category }
            : ((m.payload as Record<string, unknown> | null) ?? null),
        live: true,
      };
      setItems((list) => [ev, ...list].slice(0, MAX_FEED));
    });
    realtime.subscribe("admin");
    return () => {
      off();
      realtime.unsubscribe("admin");
    };
  }, []);
  // HTTP fallback while the socket is down
  useEffect(() => {
    if (ws === "open") return;
    const id = window.setInterval(load, POLL_MS);
    return () => window.clearInterval(id);
  }, [ws, load]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {GROUPS.map((g) => (
          <button
            key={g || "all"}
            type="button"
            aria-pressed={group === g}
            onClick={() => setGroup(g)}
            className={`h-9 cursor-pointer rounded-lg px-3 text-sm ${
              group === g
                ? "bg-nebula-500 text-white"
                : "border border-white/10 text-ink-300 hover:text-ink-100"
            }`}
          >
            {t(`admin.groups.${g || "all"}`)}
          </button>
        ))}
        <button
          type="button"
          onClick={load}
          className="ml-auto inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 px-3 text-sm text-ink-300 hover:text-ink-100"
        >
          <RefreshCw className="size-4" aria-hidden="true" /> {t("admin.reload")}
        </button>
      </div>
      <p className="text-xs text-ink-400" aria-live="polite">
        {ws === "open" && live === "ok"
          ? t("admin.liveOn")
          : live === "forbidden"
            ? t("admin.liveForbidden")
            : t("admin.liveOff", { s: POLL_MS / 1000 })}
      </p>
      {error && (
        <p className="text-sm text-danger-400" role="alert">
          {error}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem]">
          <thead>
            <tr>
              <th className={th}>{t("admin.time")}</th>
              <th className={th}>{t("admin.type")}</th>
              <th className={th}>{t("admin.object")}</th>
              <th className={th}>{t("admin.who")}</th>
              <th className={th}>{t("admin.details")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e, i) => (
              <tr key={e.id ?? `live-${i}-${e.ts}`} className={e.live ? "bg-nebula-500/10" : ""}>
                <td className={`${td} font-mono text-xs whitespace-nowrap`}>{when(e.ts)}</td>
                <td className={td}>{e.type}</td>
                <td className={td}>{e.object_key ?? "—"}</td>
                <td className={`${td} text-xs`}>{e.user ?? (e.session ? `#${e.session}` : "—")}</td>
                <td className={`${td} font-mono text-xs break-all text-ink-300`}>
                  {e.payload ? JSON.stringify(e.payload) : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <p className="py-3 text-sm text-ink-400">{t("admin.noEvents")}</p>}
      </div>
    </div>
  );
}

function UsersTab() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<AdminUser[] | null>(null);
  useEffect(() => {
    apiGet<{ items: AdminUser[] }>("/admin/users").then(
      (r) => setRows(r.items),
      () => setRows([]),
    );
  }, []);
  if (!rows)
    return <Loader2 className="size-5 animate-spin text-nebula-300" aria-label={t("admin.loading")} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem]">
        <thead>
          <tr>
            <th className={th}>{t("admin.email")}</th>
            <th className={th}>{t("admin.created")}</th>
            <th className={th}>{t("admin.lastLogin")}</th>
            <th className={th}>{t("admin.saved")}</th>
            <th className={th}>{t("admin.events")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((u) => (
            <tr key={u.id}>
              <td className={td}>
                {u.email}{" "}
                {u.is_admin && <span className="text-xs text-star-300">({t("account.admin")})</span>}
              </td>
              <td className={`${td} text-xs`}>{when(u.created_at)}</td>
              <td className={`${td} text-xs`}>{when(u.last_login_at)}</td>
              <td className={`${td} font-mono`}>{u.saved}</td>
              <td className={`${td} font-mono`}>{u.events}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="py-3 text-sm text-ink-400">{t("admin.noUsers")}</p>}
    </div>
  );
}

function FeedbackTab() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<FeedbackRow[] | null>(null);
  const [filter, setFilter] = useState<"" | FeedbackRow["status"]>("new");
  useEffect(() => {
    apiGet<{ items: FeedbackRow[] }>(`/admin/feedback${filter ? `?status=${filter}` : ""}`).then(
      (r) => setRows(r.items),
      () => setRows([]),
    );
  }, [filter]);
  const setStatus = async (id: number, status: FeedbackRow["status"]) => {
    await apiPost(`/admin/feedback/${id}/status`, { status });
    setRows((rs) => (rs ?? []).map((r) => (r.id === id ? { ...r, status } : r)));
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {(["new", "read", "done", ""] as const).map((s) => (
          <button
            key={s || "all"}
            type="button"
            aria-pressed={filter === s}
            onClick={() => setFilter(s)}
            className={`h-9 cursor-pointer rounded-lg px-3 text-sm ${
              filter === s
                ? "bg-nebula-500 text-white"
                : "border border-white/10 text-ink-300 hover:text-ink-100"
            }`}
          >
            {t(`admin.status.${s || "all"}`)}
          </button>
        ))}
      </div>
      {!rows ? (
        <Loader2 className="size-5 animate-spin text-nebula-300" aria-label={t("admin.loading")} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-ink-400">{t("admin.noFeedback")}</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((f) => (
            <li key={f.id} className={card}>
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs text-ink-400">
                <span>
                  {when(f.created_at)} · {t(`feedback.categories.${f.category}`)} · {f.page ?? ""}
                  {f.object_key ? ` · ${f.object_key}` : ""}
                </span>
                <span>{f.email ?? t("admin.noEmail")}</span>
              </div>
              <p className="mt-2 text-sm whitespace-pre-wrap text-ink-100">{f.message}</p>
              <div className="mt-2 flex gap-2">
                {(["new", "read", "done"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    aria-pressed={f.status === s}
                    onClick={() => void setStatus(f.id, s)}
                    className={`h-8 cursor-pointer rounded-lg px-2.5 text-xs ${
                      f.status === s ? "bg-nebula-500 text-white" : "border border-white/10 text-ink-300"
                    }`}
                  >
                    {t(`admin.status.${s}`)}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ReleasesTab() {
  const { t } = useTranslation();
  const [info, setInfo] = useState<ReleasesInfo | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const load = useCallback(() => {
    apiGet<ReleasesInfo>("/admin/releases").then(setInfo, () => setInfo(null));
  }, []);
  useEffect(load, [load]);

  const refresh = async (scope: string) => {
    if (!window.confirm(t("admin.confirmRefresh", { scope }))) return;
    setBusy(scope);
    setMessage(null);
    try {
      const r = await apiPost<{ removed: { files: number; bytes: number } }>("/admin/cache/refresh", {
        scope,
      });
      setMessage(t("admin.refreshed", { scope, files: r.removed.files, size: mb(r.removed.bytes) }));
      load();
    } catch (e) {
      setMessage(errorText(t, e));
    } finally {
      setBusy(null);
    }
  };
  if (!info)
    return <Loader2 className="size-5 animate-spin text-nebula-300" aria-label={t("admin.loading")} />;
  const external = Object.entries(info.cache).filter(([k]) => k.startsWith("_external/"));
  const btn =
    "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 px-2.5 text-xs text-ink-300 hover:text-ink-100 disabled:cursor-wait disabled:opacity-60";
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-300">{t("admin.releasesNote", { file: info.config_file })}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem]">
          <thead>
            <tr>
              <th className={th}>{t("admin.release")}</th>
              <th className={th}>{t("admin.state")}</th>
              <th className={th}>{t("admin.calib")}</th>
              <th className={th}>DOI</th>
              <th className={th}>{t("admin.cacheSize")}</th>
              <th className={th} />
            </tr>
          </thead>
          <tbody>
            {info.releases.map((r) => (
              <tr key={r.id}>
                <td className={td}>
                  {r.label}{" "}
                  {r.id === info.default && (
                    <span className="text-xs text-star-300">({t("admin.default")})</span>
                  )}
                </td>
                <td className={`${td} text-xs`}>
                  {r.status}
                  {!r.announced && ` · ${t("admin.notAnnounced")}`}
                </td>
                <td className={`${td} text-xs`}>{r.calib_family}</td>
                <td className={`${td} font-mono text-xs`}>{r.doi ?? "—"}</td>
                <td className={`${td} font-mono text-xs`}>
                  {r.cache.files} · {mb(r.cache.bytes)}
                </td>
                <td className={td}>
                  <button type="button" disabled={!!busy} onClick={() => void refresh(r.id)} className={btn}>
                    {busy === r.id ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="size-3.5" />
                    )}
                    {t("admin.refresh")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={card}>
        <p className="mb-2 text-sm text-ink-300">{t("admin.externalCache")}</p>
        <ul className="grid gap-1 font-mono text-xs sm:grid-cols-2">
          {external.map(([k, v]) => (
            <li key={k} className="flex justify-between gap-2">
              <span className="text-ink-300">{k.replace("_external/", "")}</span>
              <span className="text-ink-100">
                {v.files} · {mb(v.bytes)}
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={!!busy} onClick={() => void refresh("external")} className={btn}>
            <RefreshCw className="size-3.5" aria-hidden="true" /> {t("admin.refreshExternal")}
          </button>
          <button type="button" disabled={!!busy} onClick={() => void refresh("all")} className={btn}>
            <RefreshCw className="size-3.5" aria-hidden="true" /> {t("admin.refreshAll")}
          </button>
        </div>
      </div>
      {message && (
        <p className="text-sm text-ink-100" role="status">
          {message}
        </p>
      )}
      <p className="text-xs text-ink-400">{t("admin.prewarmHint")}</p>
    </div>
  );
}

/** "#admin": only for the ADMIN_EMAIL account; everything else gets a short explanation. */
export default function AdminPage({ onBack }: { onBack: () => void }) {
  const { t } = useTranslation();
  const { ready, user } = useAuth();
  const [tab, setTab] = useState<Tab>("summary");

  let body: React.ReactNode;
  if (!ready)
    body = <Loader2 className="size-5 animate-spin text-nebula-300" aria-label={t("admin.loading")} />;
  else if (!user)
    body = (
      <div className="space-y-3">
        <p className="text-sm text-ink-300">{t("admin.needLogin")}</p>
        <button
          type="button"
          onClick={auth.openLogin}
          className="h-10 cursor-pointer rounded-lg bg-nebula-500 px-4 text-sm font-medium text-white"
        >
          {t("account.login")}
        </button>
      </div>
    );
  else if (!user.is_admin) body = <p className="text-sm text-ink-300">{t("admin.notAdmin")}</p>;
  else
    body = (
      <>
        <div role="tablist" aria-label={t("admin.title")} className="flex flex-wrap gap-2">
          {TABS.map((k) => (
            <button
              key={k}
              role="tab"
              type="button"
              aria-selected={tab === k}
              onClick={() => setTab(k)}
              className={`h-10 cursor-pointer rounded-lg px-3 text-sm ${
                tab === k
                  ? "bg-nebula-500 text-white"
                  : "border border-white/10 text-ink-300 hover:text-ink-100"
              }`}
            >
              {t(`admin.tabs.${k}`)}
            </button>
          ))}
        </div>
        <div role="tabpanel">
          {tab === "summary" && <SummaryTab />}
          {tab === "live" && <LiveTab />}
          {tab === "users" && <UsersTab />}
          {tab === "feedback" && <FeedbackTab />}
          {tab === "releases" && <ReleasesTab />}
        </div>
      </>
    );

  return (
    <section
      className="glass w-full max-w-6xl space-y-5 rounded-2xl p-5 sm:p-8"
      aria-labelledby="admin-title"
    >
      <button
        type="button"
        onClick={onBack}
        className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-ink-300 hover:text-ink-100"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> {t("sources.back")}
      </button>
      <h1 id="admin-title" className="font-display text-3xl font-semibold text-ink-100">
        {t("admin.title")}
      </h1>
      {body}
    </section>
  );
}
