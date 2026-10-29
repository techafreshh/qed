// Plain REST + SSE helpers for the QED demo shell.
//
// Demo-critical rendering uses only `fetch` + `EventSource` — never
// CopilotKit — so the shell works offline against the local FastAPI app.

export interface TraceEntry {
  stage: string;
  ts?: string;
  detail?: unknown;
}

export interface RunDetail {
  run_id: string;
  paper_id: string;
  status: string;
  verdict?: string | null;
  fragile_choice?: unknown;
  trace: TraceEntry[];
  notebook_url?: string;
}

export interface Paper {
  id: string;
  title: string;
  citation?: string;
  claim?: string;
  expected_verdict?: string;
}

export interface NotebookCell {
  cell_type: string;
  source: string;
  outputs?: unknown[];
}

export interface Notebook {
  run_id: string;
  paper_id: string;
  status: string;
  verdict?: string | null;
  cells: NotebookCell[];
}

async function asJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** GET /api/papers; degrades to [] instead of crashing when unreachable. */
export async function listPapers(): Promise<Paper[]> {
  const res = await fetch("/api/papers");
  if (!res.ok) return [];
  const data = (await asJson(res)) as Paper[] | null;
  return Array.isArray(data) ? data : [];
}

/** POST /api/runs; throws an honest Error on failure (never silent). */
export async function createRun(
  paperId: string,
  claim: string,
  paperText?: string,
): Promise<{ run_id: string; status: string }> {
  const trimmed = (paperText ?? "").trim();
  const body: Record<string, string> =
    trimmed.length > 0
      ? { paper_id: paperId, claim, paper_text: trimmed }
      : { paper_id: paperId, claim };
  let res: Response;
  try {
    res = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    throw new Error(`cannot reach the QED server: ${String(err)}`);
  }
  if (res.status === 404) throw new Error("unknown paper id");
  if (!res.ok) throw new Error(`run creation failed (HTTP ${res.status})`);
  const data = (await asJson(res)) as { run_id: string; status: string };
  if (!data || typeof data.run_id !== "string")
    throw new Error("server returned a malformed run");
  return data;
}

/**
 * GET /api/runs/{id}. Returns null on 404 (unknown run) and on 409
 * (not yet complete, for notebook-shaped callers); throws an honest
 * Error otherwise.
 */
export async function fetchRun(id: string): Promise<RunDetail | null> {
  let res: Response;
  try {
    res = await fetch(`/api/runs/${encodeURIComponent(id)}`);
  } catch (err) {
    throw new Error(`cannot reach the QED server: ${String(err)}`);
  }
  if (res.status === 404 || res.status === 409) return null;
  if (!res.ok) throw new Error(`run fetch failed (HTTP ${res.status})`);
  return (await asJson(res)) as RunDetail;
}

/** GET /api/runs/{id}/notebook. Null on 404/409, honest Error otherwise. */
export async function fetchNotebook(id: string): Promise<Notebook | null> {
  let res: Response;
  try {
    res = await fetch(`/api/runs/${encodeURIComponent(id)}/notebook`);
  } catch (err) {
    throw new Error(`cannot reach the QED server: ${String(err)}`);
  }
  if (res.status === 404 || res.status === 409) return null;
  if (!res.ok) throw new Error(`notebook fetch failed (HTTP ${res.status})`);
  return (await asJson(res)) as Notebook;
}

/**
 * Subscribe to GET /api/runs/{id}/events over SSE. Returns an
 * unsubscribe function; closes the stream on error.
 */
export function openRunEvents(
  id: string,
  onEvent: (event: unknown) => void,
): () => void {
  const source = new EventSource(`/api/runs/${encodeURIComponent(id)}/events`);
  source.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data));
    } catch {
      onEvent(msg.data);
    }
  };
  source.onerror = () => source.close();
  return () => source.close();
}
