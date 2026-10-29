import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchNotebook, type Notebook } from "../lib/api";
import {
  Alert,
  Card,
  CodeBlock,
  Collapsible,
  LoadingStates,
  Tabs,
} from "../components/beUI";

export default function Notebook(): JSX.Element {
  const { id = "" } = useParams();
  const [book, setBook] = useState<Notebook | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchNotebook(id)
      .then((nb) => {
        if (cancelled) return;
        if (nb == null) setPending(true);
        else setBook(nb);
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
  if (pending)
    return (
      <Alert tone="info">
        Notebook for run <code>{id}</code> is not ready yet (run not
        complete). Watch the <Link to={`/runs/${id}`}>live trace</Link>.
      </Alert>
    );
  if (book == null) return <LoadingStates message={`Loading notebook for ${id}…`} />;

  const codeCells = book.cells.filter((c) => c.cell_type !== "markdown");
  const textCells = book.cells.filter((c) => c.cell_type === "markdown");
  const failed = book.status !== "complete";

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <Card title={`Notebook — run ${book.run_id}`}>
        {failed && (
          <Alert tone="warn">
            This run did not complete cleanly (status: {book.status}); cells
            below are the honest partial record.
          </Alert>
        )}
        <Tabs
          tabs={[
            {
              id: "code",
              label: `Code (${codeCells.length})`,
              content: (
                <div style={{ display: "grid", gap: 8 }}>
                  {codeCells.length === 0 && (
                    <Alert tone="info">No code cells recorded.</Alert>
                  )}
                  {codeCells.map((cell, i) => (
                    <div key={i}>
                      <CodeBlock code={cell.source} language="python" />
                      {(cell.outputs ?? []).length > 0 && (
                        <CodeBlock
                          code={JSON.stringify(cell.outputs, null, 2)}
                          language="json"
                        />
                      )}
                    </div>
                  ))}
                </div>
              ),
            },
            {
              id: "narrative",
              label: `Narrative (${textCells.length})`,
              content: (
                <div style={{ display: "grid", gap: 8 }}>
                  {textCells.map((cell, i) => (
                    <Card key={i}>
                      <div style={{ whiteSpace: "pre-wrap", fontSize: 14 }}>
                        {cell.source}
                      </div>
                    </Card>
                  ))}
                </div>
              ),
            },
            {
              id: "raw",
              label: "Raw JSON",
              content: (
                <CodeBlock
                  code={JSON.stringify(book, null, 2)}
                  language="json"
                />
              ),
            },
          ]}
        />
      </Card>
      <Collapsible title="Run details">
        <div style={{ fontSize: 13 }}>
          paper <code>{book.paper_id}</code> · status{" "}
          <code>{book.status}</code> · verdict{" "}
          <code>{book.verdict ?? "—"}</code>
        </div>
      </Collapsible>
      <div style={{ display: "flex", gap: 12 }}>
        <Link to={`/runs/${id}`}>← Live trace</Link>
        <Link to={`/runs/${id}/verdict`}>Verdict card →</Link>
      </div>
    </div>
  );
}
