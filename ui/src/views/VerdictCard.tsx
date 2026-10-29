import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchRun, type RunDetail } from "../lib/api";
// beUI surface: Card, AnimatedBadge, Number, Table, StreamingResponse, Alert.
import {
  Alert,
  AnimatedBadge,
  Card,
  LoadingStates,
  Number,
  StreamingResponse,
  Table,
} from "../components/beUI";

function narrationFor(run: RunDetail): string {
  if (run.verdict === "REPLICATED")
    return `The reproduced analysis supports the published claim for paper ${run.paper_id}.`;
  if (run.verdict === "FAILED" || run.verdict === "REFUTED")
    return `The reproduced analysis does not support the published claim for paper ${run.paper_id}.`;
  if (run.verdict) return `Verdict recorded: ${run.verdict}.`;
  return "The run has not reached a verdict yet — the pipeline is still working.";
}

export default function VerdictCard(): JSX.Element {
  const { id = "" } = useParams();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRun(id)
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
  }, [id]);

  if (error != null) return <Alert tone="error">{error}</Alert>;
  if (missing)
    return (
      <Alert tone="warn">
        Unknown run <code>{id}</code>. Start a new run from the{" "}
        <Link to="/">claim input</Link>.
      </Alert>
    );
  if (run == null) return <LoadingStates message={`Loading verdict for ${id}…`} />;
  if (run.status !== "complete" || run.verdict == null)
    return (
      <Alert tone="info">
        Run <code>{run.run_id}</code> is <strong>{run.status}</strong> — no
        verdict yet. Watch the <Link to={`/runs/${id}`}>live trace</Link>.
      </Alert>
    );

  const fragile =
    run.fragile_choice != null && typeof run.fragile_choice === "object"
      ? (run.fragile_choice as Record<string, unknown>)
      : null;
  const gridRows = fragile
    ? Object.entries(fragile).map(([k, v]) => ({
        choice: k,
        value: typeof v === "string" ? v : JSON.stringify(v),
      }))
    : [{ choice: "verdict", value: String(run.verdict) }];

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <Card title={`Verdict — run ${run.run_id}`}>
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <AnimatedBadge verdict={run.verdict} />
          <Number label="trace stages" value={run.trace.length} />
        </div>
      </Card>
      <Card title="Decisive grid choices">
        <Table columns={["choice", "value"]} rows={gridRows} />
      </Card>
      <Card title="What this means">
        <StreamingResponse text={narrationFor(run)} />
      </Card>
      <div style={{ display: "flex", gap: 12 }}>
        <Link to={`/runs/${id}`}>← Live trace</Link>
        <Link to={`/runs/${id}/notebook`}>Notebook →</Link>
      </div>
    </div>
  );
}
