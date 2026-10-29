import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createRun, listPapers, type Paper } from "../lib/api";
import { Alert, Card } from "../components/beUI";

const FALLBACK_PAPERS: Paper[] = [
  { id: "demo_replicated", title: "Demo replicated finding (offline)" },
  { id: "demo_failed", title: "Demo failed finding (offline)" },
];

export default function ClaimInput(): JSX.Element {
  const navigate = useNavigate();
  const [papers, setPapers] = useState<Paper[]>(FALLBACK_PAPERS);
  const [paperId, setPaperId] = useState("");
  const [claim, setClaim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listPapers()
      .then((items) => {
        if (cancelled) return;
        if (items.length > 0) {
          setPapers(items);
          setPaperId((prev) => prev || items[0].id);
        }
      })
      .catch(() => {
        // Offline: keep the fallback papers, never crash.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    if (!paperId || !claim.trim()) {
      setError("Pick a paper and paste a claim first.");
      return;
    }
    setBusy(true);
    try {
      const run = await createRun(paperId, claim.trim());
      navigate(`/runs/${run.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="New verification run">
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12 }}>
        <label style={{ display: "grid", gap: 4, fontSize: 14 }}>
          Paper
          <select
            value={paperId}
            onChange={(e) => setPaperId(e.target.value)}
            style={{ padding: 8, borderRadius: 8 }}
          >
            <option value="">— choose a paper —</option>
            {papers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 14 }}>
          Claim to verify
          <textarea
            value={claim}
            onChange={(e) => setClaim(e.target.value)}
            rows={4}
            placeholder="Paste the published claim, e.g. smaller class sizes raise test scores."
            style={{ padding: 8, borderRadius: 8 }}
          />
        </label>
        {error != null && <Alert tone="error">{error}</Alert>}
        <button
          type="submit"
          disabled={busy}
          style={{
            padding: "10px 16px",
            borderRadius: 8,
            background: "#2563eb",
            color: "#fff",
            border: 0,
            cursor: busy ? "wait" : "pointer",
            fontWeight: 700,
          }}
        >
          {busy ? "Starting run…" : "Verify claim"}
        </button>
      </form>
    </Card>
  );
}
