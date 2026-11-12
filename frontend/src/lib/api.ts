// Thin fetch wrapper. The backend error contract is {"code": "..."}; UI text comes from i18n.

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`/api/v1${path}`, { credentials: "same-origin", signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, (body as { code?: string }).code ?? `HTTP_${res.status}`);
  }
  return (await res.json()) as T;
}

export interface ReleaseInfo {
  id: string;
  label: string;
  status: "active" | "staged" | "superseded" | "retired";
  calib_family: string;
  doi: string | null;
  show_with_warning: boolean;
  notes: string;
}

export interface ReleasesResponse {
  default: string;
  releases: ReleaseInfo[];
  last_update: string | null;
}

export interface Attribution {
  key: string;
  title: string;
  text: string;
  url?: string;
  dois?: string[];
}
