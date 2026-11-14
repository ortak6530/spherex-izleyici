// The comparison currently shown on the page. The assistant sends only this id; the server reads the
// stored values itself (numbers from the browser are never used).
let lastId: string | null = null;

export const lastComparison = {
  set(id: string | null | undefined) {
    lastId = id ?? null;
  },
  get: () => lastId,
};
