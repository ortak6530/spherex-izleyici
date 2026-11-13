// Signed-in user and their saved items, shared by the top bar, the workspace and the result panels.
import { useSyncExternalStore } from "react";

import { apiDelete, apiGet, apiPost } from "./api";

export interface User {
  email: string;
  is_admin: boolean;
  created_at: string | null;
}

export interface SavedItem {
  id: number;
  kind: "object" | "comparison";
  ref: string;
  label: string;
  data: Record<string, string | number | boolean | null> | null;
  created_at: string | null;
}

interface AuthState {
  ready: boolean;
  user: User | null;
  emailMode: "emailjs" | "server_log" | "disabled" | null;
  saved: SavedItem[];
  loginOpen: boolean;
}

let state: AuthState = { ready: false, user: null, emailMode: null, saved: [], loginOpen: false };
const listeners = new Set<() => void>();

function set(patch: Partial<AuthState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

export const auth = {
  get: () => state,
  subscribe(l: () => void) {
    listeners.add(l);
    return () => listeners.delete(l);
  },

  async load() {
    try {
      const r = await apiGet<{ user: User | null; email_mode: AuthState["emailMode"] }>("/auth/me");
      set({ ready: true, user: r.user, emailMode: r.email_mode });
      if (r.user) await auth.refreshSaved();
    } catch {
      set({ ready: true }); // the site works signed-out if this fails
    }
  },

  async refreshSaved() {
    if (!state.user) return set({ saved: [] });
    try {
      const r = await apiGet<{ items: SavedItem[] }>("/me/saved");
      set({ saved: r.items });
    } catch {
      /* keep the previous list */
    }
  },

  requestCode: (email: string) =>
    apiPost<{ ok: true; expires_in_s: number; sends_left: number; delivery?: "server_log" }>(
      "/auth/request-code",
      { email },
    ),

  async verify(email: string, code: string) {
    const r = await apiPost<{ user: User }>("/auth/verify", { email, code });
    set({ user: r.user, loginOpen: false });
    await auth.refreshSaved();
    return r.user;
  },

  async logout() {
    await apiPost("/auth/logout", {});
    set({ user: null, saved: [] });
  },

  async save(kind: SavedItem["kind"], ref: string, label: string, data?: SavedItem["data"]) {
    await apiPost("/me/saved", { kind, ref, label, data: data ?? null });
    await auth.refreshSaved();
  },

  async remove(id: number) {
    await apiDelete(`/me/saved/${id}`);
    set({ saved: state.saved.filter((s) => s.id !== id) });
  },

  openLogin: () => set({ loginOpen: true }),
  closeLogin: () => set({ loginOpen: false }),
};

export function useAuth(): AuthState {
  return useSyncExternalStore(auth.subscribe, auth.get, auth.get);
}

/** Link that reopens a saved item: objects by their search text, comparisons by their object + band. */
export function savedHref(item: SavedItem): string {
  const u = new URL(window.location.origin + "/");
  const q = item.data?.q;
  if (typeof q === "string" && q) u.searchParams.set("q", q);
  const d = item.data?.d;
  if (typeof d === "number") u.searchParams.set("d", String(d));
  return u.pathname + u.search;
}
