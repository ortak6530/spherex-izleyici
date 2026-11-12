// localStorage can throw (private mode, blocked storage); the site must work without it.
const PREFIX = "spx:";

export const storage = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(PREFIX + key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string): void {
    try {
      window.localStorage.setItem(PREFIX + key, value);
    } catch {
      /* ignore */
    }
  },
};
