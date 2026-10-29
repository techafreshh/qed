# QED

*A second opinion for published science.*

QED is an agent that takes a published paper's headline claim plus its public replication package, writes its **own** analysis code from scratch (the authors' scripts are never executed), runs that code in sandboxed execution, and delivers a verdict — **REPLICATED / PARTIAL / DID NOT REPLICATE** — with the executed notebook as the receipt. Every number on the verdict card traces to an executed cell output.

Built for the Meta Global AI Developer Hackathon: Llama (Meta Model API) does the reasoning and planning, analysis code is authored via Meta's coding agent, and execution runs on Modal sandboxes.

## Status

🚧 Active build — 8-day hackathon clock. Product requirements: [`.agents/PRDs/PRD.md`](.agents/PRDs/PRD.md).

## Stack

- **Orchestrator:** Python 3.12+ / FastAPI — Llama via Meta Model API (claim extraction, spec-grid planning, failure diagnosis, verdict narration)
- **Codegen:** pluggable author port — Meta Muse Code (if headless-callable) → pi → Llama direct
- **Execution:** Modal sandboxes from frozen images (stats / ML stacks), no network egress, 5-minute hard time-box
- **UI:** React + Vite on beUI components, connected to the agent via CopilotKit (AG-UI event stream)
- **Verdicts:** deterministic coded rubric — the rubric decides, the model explains

## Setup

Requires Python 3.12+. Install and run:

```sh
pip install -r requirements.txt
cp .env.example .env   # then fill in META_API_KEY / MODAL_TOKEN for live runs
```

QED is offline-first: `QED_OFFLINE=1` (the default, see `.env.example`) serves both demo papers with zero egress and zero credit spend, so judges and operators can evaluate without keys. Set `QED_OFFLINE=0` plus real keys in `.env` to go live. Never commit `.env`.

Run the service and the gates:

```sh
make dev           # uvicorn app.main:app on :8000
make test          # full suite (credential-free)
make replay        # frozen-library replay parity
make eval          # full offline eval gate
```

### Code path: Meta, Muse, and Modal

- **Meta (Llama):** reasoning, planning, failure diagnosis, and verdict narration go through Llama via the Meta Model API (`META_API_KEY`; see `agent/llm.py`). With no key set, the offline stubs stand in and every refusal is honest.
- **Muse:** analysis code is authored via Meta's `muse-spark` coding model (`MUSE_MODEL = "muse-spark-1.3-contributor"` in `codegen/muse_backend.py`), invoked headlessly through the `pi` CLI; offline or without `pi`, a deterministic template stands in and the run is marked accordingly.
- **Modal:** sandboxed execution runs on Modal (`runner/sandbox.py:run_code` lazily imports `modal`; the live path needs `MODAL_TOKEN`), and deployment is one command:

```sh
modal deploy modal_app.py   # stable URL through Nov 8 (re-deploy to extend)
modal serve modal_app.py    # preview without deploying
```

`modal_app.py` serves the existing FastAPI app plus the static UI bundle at a fixed app name (`qed`), so the deployed URL is stable. Operator-only key insertion (via `modal secret`) and any demo video remain manual.

### Side-chat fallback

The run side-chat panel (`ui/src/copilot.tsx`) answers from the run trace over REST (`fetchRun`) plus the live AG-UI stream (`GET /api/runs/{id}/events`). CopilotKit's `useCopilotChat` is resolved through a guarded dynamic import only — when CopilotKit is disabled or the network is blocked, the verdict card and trace views still render from REST with zero config required.

## The paper library

QED validates against a frozen library of pre-vetted papers with recorded expected verdicts, sourced from large-scale replication efforts (Reproducibility Project: Psychology, Many Labs) and published failed replications. The library is the validation set **and** the demo set — every manifest records its expected verdict and the source of that expectation (PRD §10). Each manifest pins its dataset URL + sha256 + license, estimator spec, and reported numbers (`library/papers/*.yaml`); `library/schema.py:load_library` validates the contract.

| paper | expected verdict | source |
| --- | --- | --- |
| Card & Krueger (1994), minimum wage | REPLICATED | original Table 3, pinned CSV mirror |
| Hsee (1998) less-is-better via Many Labs 2 | REPLICATED | Klein et al. (2018), Many Labs 2 |
| Zhong & Liljenquist (2006) Macbeth via Many Labs 2 | FAILED | failed replication, Klein et al. (2018) |
| Reinhart & Rogoff (2010) debt, Herndon-Ash-Pollin correction | PARTIAL | Herndon, Ash & Pollin (2013) |

QED writes its own analysis code from scratch against the public replication package — it never executes the authors' scripts. Execution happens only in locked-down sandboxes (frozen images, no network egress, 5-minute hard time-box), and the executed notebook is the receipt behind every verdict card.

## Offline cut path (no keys, no network)

```sh
QED_OFFLINE=1 make test && make replay && make eval   # each exits 0
QED_OFFLINE=1 python3 scripts/demo_offline.py        # completed-run probe chain
```

`make replay` replays the frozen library (`scripts/replay.py` over `evals/replay.py`), `make eval` runs the full offline eval gate (replay parity, adversarial refusal probes, no-fabrication check), and `make demo-offline` serves the offline demo UI (`QED_OFFLINE=1` uvicorn with paste-a-claim curl lines). The `scripts/` entry points double as documentation: replay, eval table, and the `demo_replicated` probe chain that asserts the 200/200/202/200/200/200 acceptance sequence.

## License

MIT — see [LICENSE](LICENSE).
