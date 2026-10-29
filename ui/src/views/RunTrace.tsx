import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchRun, openRunEvents, type RunDetail } from "../lib/api";
import {
  AgentActivity,
  Alert,
  Card,
  LoadingStates,
  ToolResult,
} from "../components/beUI";

function detailText(detail: unknown): string {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export default function RunTrace(): JSX.Element {
  const { id = "" } = useParams();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<unknown[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let close: (() => void) | null = null;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function poll(): Promise<void> {
      try {
        const detail = await fetchRun(id);
        if (!cancelled) {
          if (detail == null) setError("Unknown run id.");
          else setRun(detail);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    }

    try {
      close = openRunEvents(id, (ev) => {
        if (!cancelled) setEvents((prev) => [...prev, ev]);
      });
    } catch {
      // SSE unavailable: polling below still drives the trace.
    }
    void poll();
    timer = setInterval(() => void poll(), 2000);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      if (close) close();
    };
  }, [id]);

  if (error != null) {
    return <Alert tone="error">{error}</Alert>;
  }
  if (run == null) {
    return <LoadingStates message={`Loading run ${id}…`} />;
  }

  const pending = run.status !== "complete";
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <Card title={`Run ${run.run_id} — ${run.status}`}>
        <div style={{ display: "grid", gap: 10 }}>
          {run.trace.map((entry, i) => (
            <AgentActivity
              key={i}
              stage={entry.stage}
              active={pending && i === run.trace.length - 1}
              detail={
                entry.detail == null ? undefined : (
                  <ToolResult
                    name={entry.stage}
                    output={detailText(entry.detail)}
                  />
                )
              }
            />
          ))}
          {pending && <LoadingStates message="Extraction → verdict in progress…" />}
        </div>
      </Card>
      {events.length > 0 && (
        <Card title="Live events">
          <div style={{ display: "grid", gap: 6 }}>
            {events.slice(-8).map((ev, i) => (
              <ToolResult key={i} name="sse" output={detailText(ev)} />
            ))}
          </div>
        </Card>
      )}
      <div style={{ display: "flex", gap: 12 }}>
        <Link to={`/runs/${id}/verdict`}>Verdict card →</Link>
        <Link to={`/runs/${id}/notebook`}>Notebook →</Link>
      </div>
    </div>
  );
}
