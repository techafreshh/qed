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

Coming with the walking skeleton. Required keys will live in `.env` (see `.env.example`): `META_API_KEY`, `MODAL_TOKEN`, plus `QED_OFFLINE` and `QED_CODEGEN_BACKEND` mode flags.

## The paper library

QED validates against a frozen library of pre-vetted papers with recorded expected verdicts, sourced from large-scale replication efforts (Reproducibility Project: Psychology, Many Labs) and published failed replications. The library is the validation set **and** the demo set — every manifest records its expected verdict and the source of that expectation (PRD §10).

## License

MIT — see [LICENSE](LICENSE).
