// Run a server job: live progress over WebSocket when available, HTTP polling always as a fallback.
import { apiGet, ApiError, type JobState } from "./api";
import { realtime } from "./realtime";

export type ProgressStep = { step: string; [k: string]: unknown };

export async function runJob<T>(
  start: () => Promise<{ job_id: string }>,
  onProgress?: (s: ProgressStep) => void,
  signal?: AbortSignal,
): Promise<T> {
  const { job_id } = await start();
  const topic = `job:${job_id}`;
  let wake: (() => void) | null = null;
  const off = realtime.onMessage((m) => {
    if (m.job_id !== job_id) return;
    if (m.type === "progress") onProgress?.(m as unknown as ProgressStep);
    if (m.type === "job_done" || m.type === "job_error") wake?.();
  });
  realtime.subscribe(topic);
  try {
    let seen = 0;
    for (let i = 0; i < 600; i++) {
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      const j = await apiGet<JobState<T>>(`/jobs/${job_id}`);
      // Replay steps the socket did not deliver (e.g. socket closed)
      for (const s of j.steps.slice(seen)) onProgress?.(s);
      seen = j.steps.length;
      if (j.status === "done") return j.result as T;
      if (j.status === "error") throw new ApiError(502, j.error?.code ?? "JOB_FAILED");
      // With a live socket we are woken up on completion; otherwise poll every ~1.5 s
      await new Promise<void>((resolve) => {
        wake = resolve;
        window.setTimeout(resolve, 1500);
      });
    }
    throw new ApiError(504, "JOB_TIMEOUT");
  } finally {
    off();
    realtime.unsubscribe(topic);
  }
}
