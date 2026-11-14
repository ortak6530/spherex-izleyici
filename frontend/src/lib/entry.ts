// Welcome-screen choice: remembered for this browser tab's session only (sessionStorage), never across visits.
const KEY = "spx:entered";
const DEEP_HASHES = new Set(["#admin", "#kaynaklar"]);

export const entryChoice = {
  get(): boolean {
    try {
      return window.sessionStorage.getItem(KEY) === "1";
    } catch {
      return false;
    }
  },
  set(): void {
    try {
      window.sessionStorage.setItem(KEY, "1");
    } catch {
      /* storage blocked: the screen simply shows again next time */
    }
  },
  clear(): void {
    try {
      window.sessionStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  },
};

/** Object links (?q=…), shared comparisons (?q=&d=&compare=1) and #admin / #kaynaklar skip the screen. */
export function hasDeepLink(loc: Location = window.location): boolean {
  return new URLSearchParams(loc.search).has("q") || DEEP_HASHES.has(loc.hash);
}
