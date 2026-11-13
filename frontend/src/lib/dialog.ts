// Open/close a <dialog> as a modal, with a plain-attribute fallback (old browsers, jsdom in tests).
export function syncDialog(d: HTMLDialogElement | null, open: boolean) {
  if (!d) return;
  if (open && !d.open) {
    if (typeof d.showModal === "function") d.showModal();
    else d.setAttribute("open", "");
  }
  if (!open && d.open) {
    if (typeof d.close === "function") d.close();
    else d.removeAttribute("open");
  }
}
