// Thin fetch wrapper. Every mutating call carries the header the API checks as a CSRF guard.
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function handle<T>(r: Response): Promise<T> {
  if (r.ok) return r.json() as Promise<T>;
  let msg = `Request failed (${r.status}).`;
  try {
    const body = await r.json();
    if (typeof body.detail === "string") msg = body.detail;
  } catch {
    /* keep default */
  }
  if (r.status === 401 && !location.pathname.startsWith("/login") && !location.pathname.startsWith("/auth")) {
    location.href = "/login";
  }
  throw new ApiError(r.status, msg);
}

const H = { "x-requested-with": "groundwork" };

export const api = {
  get: <T,>(url: string) => fetch(url, { credentials: "same-origin" }).then((r) => handle<T>(r)),
  send: <T,>(method: string, url: string, body?: unknown) =>
    fetch(url, {
      method,
      credentials: "same-origin",
      headers: { ...H, "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then((r) => handle<T>(r)),
  upload: <T,>(url: string, form: FormData) =>
    fetch(url, { method: "POST", credentials: "same-origin", headers: H, body: form }).then((r) => handle<T>(r)),
};

export type Me = {
  id: string;
  email: string;
  display_name: string;
  team: string;
  role: "contributor" | "analyst" | "admin";
  org_name: string;
  app_name: string;
  ai_enabled: boolean;
  transcription_enabled: boolean;
  live_enabled: boolean;
  live_local: boolean;
  review_minutes: number;
  live_auto_threshold: number;
};

export type ProcessRow = {
  id: string;
  name: string;
  description: string;
  parent_id: string | null;
  status: string;
  owner_email: string;
  artifact_count: number;
  board_count: number;
};

export type Artifact = {
  id: string;
  title: string;
  description: string;
  kind: string;
  layer: string;
  frequency: string;
  source_system: string;
  maintained_by: string;
  personal_info: string;
  original_filename: string;
  size_bytes: number;
  status: string;
  uploaded_at: string;
  uploaded_by: string | null;
  scan: string;
  processes: { id: string; name: string }[];
  profile: { summary?: string; review_flags?: string[]; sheets?: { name: string; state: string; formulas: number; dimensions: string }[]; preview?: string } | null;
};

export type BoardRow = {
  id: string;
  title: string;
  process_id: string | null;
  process_name: string | null;
  version: number;
  updated_at: string;
  personal_info: boolean;
  node_count: number;
  session_pass?: "overview" | "detail";
  perspective?: string;
  doc?: { nodes: any[]; edges: any[]; viewport: any };
  rules?: any[];
};

export type Draft = {
  id: string;
  mode: "sop" | "workflow" | "questions" | "review" | "combine";
  provider: string;
  model: string;
  created_at: string;
  board_version: number;
  markdown: string;
  proposal: { nodes?: any[]; edges?: any[]; changes?: any[]; summary?: string; open_questions?: string[]; doc_kind?: string; rules?: any[] | null; parking_done?: string[] } | null;
  status: string;
};
