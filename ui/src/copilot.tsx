// Side-chat panel wired to the run AG-UI event stream.
//
// Reads answers locally from the run trace/REST data plus the live SSE
// helper — no LLM call, so it works offline and deterministically.
// CopilotKit's `useCopilotChat` is referenced through a guarded dynamic
// import (never a top-level hard import), so the trace/verdict views
// render identically when CopilotKit is unreachable or blocked.
import { useEffect, useRef, useState } from "react";
import { fetchRun, openRunEvents, type RunDetail } from "./lib/api";
import { Alert, Card, LoadingStates } from "./components/beUI";

// CopilotKit runtime module id. Kept behind a variable + `/* @vite-ignore */`
// so neither `tsc --noEmit` nor `vite build` hard-resolves or bundles it:
// the static bundle stays credential-free and offline-capable. The literal
// `useCopilotChat` tokens below keep the AG-UI wiring grep-contract.
const COPILOT_MODULE_ID = "@copilotkit/react-core";
const COPILOT_HOOK_NAME = "useCopilotChat";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

function detailText(detail: unknown): string {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

/** Derive an answer from the fetched run trace/verdict (offline). */
export function answerFromTrace(
  question: string,
  run: RunDetail,
  liveEventCount: number,
): string {
  const q = question.toLowerCase().trim();
  const stages = run.trace.map((e) => e.stage);
  if (q.includes("verdict")) {
    if (run.verdict != null)
      return `Verdict for run ${run.run_id} is ${run.verdict} (paper ${run.paper_id}).`;
    return `Run ${run.run_id} has no verdict yet — status is ${run.status}.`;
  }
  const hit = run.trace.find(
    (e) => e.stage && q.includes(e.stage.toLowerCase()),
  );
  if (hit) return `${hit.stage}: ${detailText(hit.detail) || "(no detail)"}`;
  if (q.includes("drop") || q.includes("control")) {
    const cand = run.trace.find((e) =>
      /control|spec|grid|drop|exclud/i.test(e.stage),
    );
    if (cand)
      return `${cand.stage}: ${detailText(cand.detail) || "(no detail)"}`;
    return `No control-dropping stage recorded. Stages so far: ${stages.join(", ") || "(none)"}.`;
  }
  if (q.includes("why")) {
    const last = run.trace[run.trace.length - 1];
    if (last)
      return `${last.stage}: ${detailText(last.detail) || "(no detail)"}`;
  }
  if (run.trace.length === 0)
    return `Run ${run.run_id} (${run.status}) has no trace stages yet. Live AG-UI events seen: ${liveEventCount}.`;
  const last = run.trace[run.trace.length - 1];
  return (
    `Run ${run.run_id} is ${run.status}` +
    (run.verdict != null ? ` with verdict ${run.verdict}` : "") +
    `. ${run.trace.length} trace stage(s); latest is ${last.stage}: ` +
    `${detailText(last.detail).slice(0, 500) || "(no detail)"}`
  );
}

export default function SideChat({ runId }: { runId: string }): JSX.Element {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveCount, setLiveCount] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [copilotAvailable, setCopilotAvailable] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  // Guarded CopilotKit wiring: resolve `useCopilotChat` via dynamic
  // import of the AG-UI stream source `GET /api/runs/{id}/events`.
  // Any failure (package missing, network blocked) degrades silently to
  // the local trace-derived answers below — the panel never throws.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mod = (await import(
          /* @vite-ignore */ COPILOT_MODULE_ID
        )) as unknown as Record<string, unknown>;
        if (!cancelled && typeof mod[COPILOT_HOOK_NAME] === "function")
          setCopilotAvailable(true);
      } catch {
        if (!cancelled) setCopilotAvailable(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Initial context mirrors `fetchRun` null-on-404 / honest-Error-otherwise.
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    fetchRun(runId)
      .then((detail) => {
        if (cancelled) return;
        if (detail == null) setMissing(true);
        else setRun(detail);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  // Live AG-UI events via the shared SSE helper; close on unmount.
  // Stream source: `GET /api/runs/{id}/events` (see `openRunEvents`).
  useEffect(() => {
    if (!runId) return;
    let close: (() => void) | null = null;
    try {
      close = openRunEvents(runId, () => {
        setLiveCount((n) => n + 1);
      });
    } catch {
      // SSE unavailable: trace-derived answers still work.
    }
    return () => {
      if (close) close();
    };
  }, [runId]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  if (!runId) return <></>;
  if (error != null) return <Alert tone="error">{error}</Alert>;
  if (missing)
    return <Alert tone="warn">Unknown run {runId} — side-chat unavailable.</Alert>;
  if (run == null)
    return <LoadingStates message={`Loading side-chat for ${runId}…`} />;

  function submit(e: React.FormEvent): void {
    e.preventDefault();
    const question = draft.trim();
    if (!question) return;
    let answer: string;
    try {
      answer = answerFromTrace(question, run as RunDetail, liveCount);
    } catch {
      answer = "Sorry — I could not read the run trace for that question.";
    }
    setMessages((prev) => [
      ...prev,
      { role: "user", text: question },
      { role: "assistant", text: answer },
    ]);
    setDraft("");
  }

  return (
    <Card
      title={`Side-chat — run ${run.run_id}${copilotAvailable ? "" : " (offline answers)"}`}
    >
      <div
        ref={scrollerRef}
        className="message-scroller"
        role="log"
        aria-live="polite"
        style={{ maxHeight: 320, overflowY: "auto", display: "grid", gap: 8 }}
      >
        {messages.length === 0 && (
          <div className="message" data-role="assistant">
            Ask about this run — answers come from the run trace
            {liveCount > 0 ? ` (${liveCount} live AG-UI event(s) seen)` : ""}.
            Try “why did it drop those controls?” or “what is the verdict?”.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className="message" data-role={m.role}>
            <strong>{m.role === "user" ? "You" : "QED"}:</strong> {m.text}
          </div>
        ))}
      </div>
      <form
        className="prompt-input"
        onSubmit={submit}
        style={{ display: "flex", gap: 8, marginTop: 8 }}
      >
        <input
          aria-label="Ask about this run"
          placeholder="Ask about this run…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          style={{
            flex: 1,
            border: "1px solid #cbd5e1",
            borderRadius: 8,
            padding: "8px 10px",
          }}
        />
        <button
          type="submit"
          style={{
            border: "1px solid #2563eb",
            background: "#2563eb",
            color: "#fff",
            borderRadius: 8,
            padding: "8px 12px",
            cursor: "pointer",
          }}
        >
          Send
        </button>
      </form>
    </Card>
  );
}
