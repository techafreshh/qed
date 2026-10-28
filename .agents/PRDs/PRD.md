# PRD — QED: A Second Opinion for Published Science

**Project:** QED — agent that independently re-analyzes published findings and delivers a replication verdict with receipts.
**Build context:** Meta Global AI Developer Hackathon. Submission due **Nov 4, 9:00 PM ET (Nov 5, 02:00 WAT)**; demo live through judging **Nov 5–8**. 8-day plan: D1 = Oct 28 → D8 = Nov 4 (submit).
**Build mode:** pi-dark-factory (unattended laps on GitHub issues). This PRD is the backlog source; the **Operator Checklist (§15) is explicitly NOT sliceable into issues.**

---

## 1. Executive Summary

QED is *"a second opinion for published science."* It takes a paper's headline claim plus its published replication package, **writes its own analysis code from scratch** (it never executes the authors' scripts), runs that code in Modal sandboxes, debugs its own failures, and delivers a deterministic verdict — **REPLICATED / PARTIAL / DID NOT REPLICATE** — with the executed notebook as the receipt.

It is a mechanic re-running the engine, not a critic reviewing the car: it checks whether the code + data produce the claimed numbers, never whether the paper is "true."

**MVP goal:** claim in → executed notebook out → correct verdict on a frozen library of pre-vetted papers (including at least one famous failure), in <10 minutes wall-clock, deployed at a stable URL, with a fully offline fallback for the live demo.

**Sponsor alignment (the Stage One story):** Llama (Meta Model API) does the reasoning and planning; analysis code is authored by Meta's coding agent (Muse Code) where callable headless, with honest fallbacks; execution runs on Modal sandboxes.

## 2. Mission

**Make replication checking cheap enough to actually happen.**

Core principles:
1. **Receipts, not vibes** — every number on the verdict card traces to an executed cell output.
2. **The rubric decides, the model explains** — verdict logic is deterministic, unit-tested code; Llama only narrates it.
3. **Own code only** — the agent re-derives the analysis; authors' scripts are never executed. (Say this sentence verbatim to any judge who asks "isn't this just running someone's code?")
4. **Honest failure** — max 3 debug iterations, then failure is reported as failure. Refusing to fabricate is a feature, not a bug.
5. **Frugal by construction** — free/hackathon credits only: frozen images, small `max_tokens`, cached demo runs, daily credit checks.

## 3. Target Users

- **Hackathon judges (primary).** Technical, ~3 minutes of attention. Need to see: the loop working live, a failure verdict (the product's headline), sponsor tech on screen. Technical comfort: high.
- **Researchers / journalists (secondary).** Paste a claim, read a verdict card and notebook. Technical comfort: medium; the verdict card must be self-explanatory.
- **The CI / factory verifier (non-human).** Must be able to accept the build with **zero external credentials and zero credit spend** — every test and acceptance probe runs in offline mode.

## 4. MVP Scope

### In scope

**Core functionality**
- [ ] Claim extraction: Llama turns paper abstract/PDF text + claim statement into a falsifiable spec (dataset, estimator, headline number(s), significance claim)
- [ ] Independent re-analysis: analysis code authored via a **pluggable codegen port** — backends: `muse` (Meta Muse Code CLI, subprocess; default iff D1 spike proves headless invocation), `pi` (pi CLI subprocess), `llama_direct` (direct Llama codegen)
- [ ] Spec grid: small grid over analytical choices (controls in/out, SE choices, sample windows) to test fragility; the fragile choice is named in every non-clean verdict
- [ ] Sandboxed execution on Modal: 2 frozen images (see §8), no network egress except whitelisted pip index, 5-minute hard time-box per run, run log (code hash, image hash, duration, verdict)
- [ ] Debug loop: failures (import errors, shape mismatches, non-convergence) go back to the code author with the traceback, max **3 iterations**, then honest failure artifact
- [ ] Deterministic verdict rubric (§10) as a pure function; Llama explains the verdict, never decides it
- [ ] Frozen paper library: ≥4 papers, each with a manifest recording expected verdict + its source
- [ ] Verdict card + live run trace + executed notebook viewer — React UI built on **beUI** components, connected to the agent via **CopilotKit** (AG-UI event stream)
- [ ] Copilot panel: judges can interrogate the run mid-flight ("why did it drop those controls?") — CopilotKit chat over the same event stream
- [ ] Paste-a-claim flow for demo onboarding
- [ ] Offline demo mode: `QED_OFFLINE=1` serves both demo papers fully cached, runnable with network disabled

**Technical**
- [ ] Ship a CI workflow (`.github/workflows/ci.yml`) as a first-lap deliverable; **the full test suite passes with no Meta/Modal credentials** (offline stubs)
- [ ] SQLite persistence: papers, run log, verdict history
- [ ] Recursion guard: refuse to run codegen/orchestration when `OPENCODE_INVOKED_BY` or `QED_AGENT_DEPTH` is set
- [ ] Eval harnesses: `make replay` (library replay), 4 adversarial probes, no-fabrication checker

**Deployment**
- [ ] Live deployment on Modal (web endpoint, stable URL through Nov 8)
- [ ] Offline cached fallback rehearsed as the mid-demo cut path

### Out of scope (v1)

- Stata/.do chains; any licensed software (Stata, SAS, MATLAB)
- Datasets >100MB; single runs >5 minutes
- Literature review, summarization, or any "explain the paper" feature
- Languages other than Python
- Multi-user auth, rate-limited public writes beyond a simple cap
- Baseten/Fireworks fallback providers (no keys exist; the provider interface stays pluggable, v1 retries Meta API directly)

## 5. User Stories

1. As a **judge**, I paste a claim and watch the run trace live (extraction → codegen → sandbox → verdict), so I can see the agent actually work rather than watch a canned video.
2. As a **judge**, I see a **DID NOT REPLICATE** verdict with the exact fragile analytical choice named ("result depends on excluding 2020; with 2020 included, p = 0.31"), so I understand the product's value — everyone demos success; this is the product.
3. As a **researcher**, I open the executed notebook, so I can verify with my own eyes that no number was fabricated.
4. As a **judge on bad venue wifi**, I use offline mode, so the demo never stalls — the cut to cached notebooks is rehearsed, not improvised.
5. As an **operator**, I run `make replay`, so every frozen paper's verdict matches its recorded expectation — a mismatch is a build bug, not a discovery.
6. As a **developer**, I run the full test suite with no Meta/Modal credentials, so CI stays green and free.
7. As an **auditor**, I read the run log (code hash, image hash, duration, verdict), so every verdict is reproducible and auditable.
8. As a **judge**, I ask the running agent questions in a side chat ("why did it drop those controls?"), so I can probe the reasoning instead of just watching it stream.

## 6. Core Architecture & Directory Structure

```
qed/
├── .agents/PRDs/PRD.md        # this file
├── app/                       # FastAPI application
│   ├── main.py                # app factory, static mount, routers
│   ├── api/                   # /health, /api/papers, /api/runs
│   └── static/                # built React bundle
├── ui/                        # React + Vite source (beUI components throughout)
│   ├── src/copilot.tsx        # CopilotKit provider → FastAPI AG-UI endpoint
│   └── src/views/             # claim input, run trace, verdict card, notebook
├── agent/                     # orchestrator stages
│   ├── extract.py             # claim → falsifiable spec (Llama)
│   ├── grid.py                # spec-grid planner
│   ├── diagnose.py            # traceback → repair loop (≤3)
│   └── explain.py             # Llama verdict narration
├── codegen/                   # pluggable code-author port
│   ├── base.py                # CodegenBackend interface
│   ├── muse_backend.py        # Meta Muse Code CLI subprocess (spike-gated)
│   ├── pi_backend.py          # pi CLI subprocess
│   └── llama_backend.py       # direct Llama codegen fallback
├── runner/                    # Modal sandbox execution
│   ├── images/                # stats.Dockerfile, ml.Dockerfile (frozen)
│   ├── sandbox.py             # run_code(): time-box, hash+duration logging
│   └── offline.py             # cached-run replay for QED_OFFLINE=1
├── rubric/
│   └── verdict.py             # deterministic rubric — pure functions
├── library/
│   ├── schema.py              # PaperManifest model
│   ├── papers/*.yaml          # frozen manifests (expected verdict + source)
│   └── candidates.md          # sourcing/vetting report (pre-freeze)
├── evals/
│   ├── replay.py              # library replay harness
│   ├── probes.py              # 4 adversarial probes
│   └── nofabrication.py       # verdict-card numbers ↔ cell outputs
├── db/models.py               # SQLite: papers, runs, artifacts
├── tests/                     # pytest; green with zero external credentials
├── Makefile                   # make dev / test / replay / demo-offline
├── .env.example               # META_API_KEY, MODAL_TOKEN, QED_OFFLINE, QED_CODEGEN_BACKEND
├── LICENSE                    # MIT
└── README.md                  # setup, Meta model usage, Modal usage, library + sources
```

**Pipeline:** extract → plan spec grid → author code (codegen port) → execute (Modal sandbox) → diagnose failures (loop ≤3) → rubric verdict → Llama explanation → render card + notebook.

**Isolation rule:** code *authoring* runs in a container whose egress is limited to Meta endpoints; analysis *execution* runs in the locked sandbox with no egress except the whitelisted pip index. Authors' scripts are never executed anywhere.

**Key patterns:**
- **`QED_OFFLINE=1` dual-purpose mode** — deterministic cached runs. It is simultaneously (a) the hackathon's offline-demo requirement and (b) the acceptance-test mode: factory verify scenarios and CI never need Meta/Modal keys or credits.
- **One event stream, two consumers** — the orchestrator emits typed stage events; the REST/SSE contract (§11) serves artifacts and acceptance scenarios, and the same run is mirrored as AG-UI protocol events for the CopilotKit UI. Demo-critical views (trace, verdict card, notebook) render from our own state, so CopilotKit is the interactive layer, never a single point of failure.
- **Codegen port** — one interface, three backends; the D1 spike (`muse --help` / headless exec probe) decides the default; the port protects the schedule from Muse auth/CLI surprises.
- **Rubric as pure function** — structured run results in, verdict out; no model calls inside.

## 7. Tools / Features

**Orchestrator (Llama via Meta Model API):**
- *Extract:* prose + abstract/PDF text → falsifiable spec JSON (validated against a pydantic schema; malformed → re-ask ≤2, then refuse).
- *Plan:* spec grid over {controls in/out, SE choice, sample window} — bounded (≤8 cells v1).
- *Diagnose:* traceback + code + spec → targeted repair instruction (loop ≤3).
- *Explain:* rubric verdict + grid results → verdict-card narration with the fragile choice named. Small `max_tokens` per call.

**Codegen port (`CodegenBackend.author(spec, dataset_profile, prior_traceback=None) -> code`):**
- `muse_backend`: subprocess to Muse Code CLI in non-interactive mode. **D1 spike decides viability** (public docs do not yet confirm a headless flag). Auth must work non-interactively in a container.
- `pi_backend`: subprocess to `pi` with a pinned prompt template.
- `llama_backend`: single-shot structured codegen via Meta Model API.
- All backends: recursion guard first; output code is written to disk; never executed on the host — only inside the sandbox.

**Sandbox runner:** `run_code(code, image, data, timebox=300s)` → stdout/stderr, produced notebook, cell outputs, exit status; logs code sha256, image digest, duration. Time-box kill is hard.

**Offline runner:** replays cached run artifacts (notebook + verdict + trace) keyed by paper id; used by demo mode and all acceptance scenarios.

**Verdict card:** headline comparison (claimed vs. reproduced), significance bands, spec-grid heat ("holds here / breaks here"), fragile choice, receipt links (notebook, run log).

**UI — concrete beUI component mapping (categories: agents / motion / blocks):**
| Surface | beUI component |
|---|---|
| Live run trace (extraction → codegen → sandbox → verdict) | `agent-activity` |
| Sandbox stdout/stderr and tool outputs | `tool-result` |
| Generated analysis code + notebook cells | `code-block` |
| Copilot chat panel (CopilotKit `useCopilotChat`) | `message` + `message-scroller` + `prompt-input` |
| Llama verdict narration | `streaming-response` + `citations` |
| Verdict card (REPLICATED / PARTIAL / FAILED) | `card` + `animated-badge` + `number` (claimed-vs-reproduced count-up) |
| Spec-grid "holds here / breaks here" | `table` |
| Run progress during the ~10-min loop | `loading-states` (+ optional `dynamic-island` status pill) |
| Views (trace / notebook / verdict), warnings, spec details | `tabs`, `alert`, `collapsible` |

## 8. Technology Stack

- **Python 3.12+ compatible code.** Modal images pin **3.12**; the factory's instabox build box runs **3.13.5** — code must run on both (no 3.12-only syntax, no 3.13-only stdlib reliance).
- **Backend:** FastAPI, uvicorn, pydantic v2, SQLite (stdlib `sqlite3` or SQLModel), httpx for Meta Model API, Modal SDK.
- **Frontend:** React + Vite, built to a static bundle served by FastAPI (no SSR). **beUI** (agents/motion/blocks) supplies every UI surface; **CopilotKit** React SDK provides the UI↔agent connection via the **AG-UI event protocol** — FastAPI emits AG-UI events directly from the orchestrator (no Node runtime sidecar; CopilotKit's React SDK consumes AG-UI-compliant backends). Contingency: if the CopilotKit integration drags past D4, trace/verdict/notebook views render from plain REST+SSE state — nothing demo-critical depends on it.
- **Notebooks:** nbformat/nbclient (generate + execute + render).
- **Stats stack (frozen image `stats`):** pandas, numpy, statsmodels, scipy, matplotlib, nbformat, nbclient.
- **ML stack (frozen image `ml`):** stats image + scikit-learn.
- **Tests:** pytest (+ respx/httpx mocks for the Meta client; fake sandbox for runner tests).

## 9. Security & Configuration

- Secrets in `.env` only (`.env.example` committed): `META_API_KEY`, `MODAL_TOKEN`, `QED_OFFLINE`, `QED_CODEGEN_BACKEND`. Never committed, never echoed into logs or receipts.
- Sandbox restrictions: whitelisted pip packages only; no egress except whitelisted index; hard time-box kill; resource-capped.
- No auth in v1; POST endpoints rate-limited; read endpoints public.
- Recursion guard: codegen and orchestrator entrypoints refuse when `OPENCODE_INVOKED_BY` or `QED_AGENT_DEPTH` is set.
- Data licensing: every library manifest records the dataset license; nothing is redistributed in violation of it (fetch-and-cache with sha256 pinning).

## 10. Paper Library & Verdict Rubric

**Library requirements (frozen by end of D2):** ≥4 papers, every one pre-vetted: public replication package, Python-readable data (CSV/parquet; `.dta` acceptable only if the estimator is re-implementable in statsmodels), runtime <5 min in sandbox, data <100MB. Mix: ≥1 famous failure + ≥2 clean replications. Field priority by data ergonomics: (1) psychology/political science with tidy CSVs + OLS/logit; (2) small UCI-scale ML; (3) economics only where already Python-friendly. Stata-only chains are excluded on sight. Sourcing bias: Reproducibility Project: Psychology and Many Labs (public data, simple estimators, recorded replication outcomes).

**Manifest per paper:** id, citation, claim text, dataset URL + sha256 + license note, estimator spec, reported numbers, **expected verdict + source of that expectation**.

**Rubric (coded before any agent work; thresholds v1):**
- **REPLICATED:** headline estimate within ±10% (or exact at reported rounding) AND same sign AND same significance band.
- **PARTIAL:** same sign + significance, but magnitude outside tolerance — or the result holds only under a subset of the reasonable spec grid.
- **FAILED:** sign flip, significance loss across the reasonable spec grid, or claimed numbers not derivable from data + stated method.
- Every non-clean verdict names the fragile choice (e.g., "result depends on excluding 2020; with 2020 included, p = 0.31").

**Hard eval gates:**
1. **Library replay:** run all frozen papers; verdicts must match recorded expectations. A mismatch is a build bug, not a discovery.
2. **Adversarial probes (4):** malformed package (missing file), underspecified claim, package needing an excluded dependency, 15-min-runtime paper — must refuse or degrade honestly, never fabricate.
3. **No-fabrication:** every number on the verdict card must trace to a cell output. Untraced numbers = fail.
4. **Live-run budget:** full claim→verdict on a frozen paper in <10 min wall-clock; ≤3 debug iterations typical.

**Kill rule:** fewer than **4** fully replay-matching papers (≥1 failure + ≥2 replicates) at the **end-of-D2 freeze decision** → project dies; no extensions; no sunk cost.

## 11. API Specification

- `GET /health` → `200 {"ok": true}`
- `GET /api/papers` → `200 [{"id", "title", "claim", "expected_verdict", "source"}]`
- `POST /api/runs` `{"paper_id": "...", "claim": "..."}` → `202 {"run_id": "run_...", "status": "queued"}`; invalid input → `422` (never 500); unknown paper → `404`
- `GET /api/runs/{id}` → `200 {"status": "queued|running|complete|failed", "verdict": "REPLICATED|PARTIAL|FAILED|null", "fragile_choice": "...|null", "trace": [{"stage", "ts", "detail"}], "notebook_url": "...|null"}`; unknown id → `404`
- `GET /api/runs/{id}/notebook` → `200` executed notebook JSON; unknown id → `404`; not-yet-complete → `409`
- `GET /api/runs/{id}/events` → SSE stream of **AG-UI protocol events** (`RUN_STARTED`, `TEXT_MESSAGE_CONTENT`, `TOOL_CALL_START`/`RESULT`, `RUN_FINISHED`) mirroring the orchestrator trace — the CopilotKit UI's agent channel; unknown id → `404`
- `/` serves the UI static bundle.

Example:
```json
POST /api/runs
{"paper_id": "minwage_teen_employment", "claim": "A 10% rise in the minimum wage reduces teen employment by 1–3%."}
→ 202 {"run_id": "run_01HQAR3", "status": "queued"}
```

## 12. Success Criteria

- [ ] Live demo: 2 papers end-to-end — 1 REPLICATED, 1 DID NOT REPLICATE — each <10 min
- [ ] `make replay` green on all frozen papers (floor: 4, incl. ≥1 failure + ≥2 replicates)
- [ ] All 4 adversarial probes refuse/degrade honestly; zero fabricated numbers
- [ ] Offline mode serves both demo papers with network disabled — rehearsed as the mid-demo cut
- [ ] Stable live URL through Nov 8; full test suite green with no external credentials
- [ ] Video ≤3 min highlighting work built during the hackathon; submitted before Nov 4, 9:00 PM ET

## 13. Implementation Phases

- **Phase 1 — Foundation & freeze (D1–D2, Oct 28–29):** walking skeleton + CI; config/secrets; Meta Model API client + offline stub; library schema; deterministic rubric; Modal harness + image Dockerfiles; codegen port + Muse headless spike; paper sourcing/vetting report. **Validation:** tests green credential-free; freeze decision made by end of D2 (kill or proceed).
- **Phase 2 — The loop (D3–D4, Oct 30–31):** extraction; spec grid + fragility; debug loop; end-to-end claim→verdict on 1 paper; replay harness; verdict card + notebook UI. **Validation:** one paper replays to its expected verdict.
- **Phase 3 — Hardening & deploy (D5–D6, Nov 1–2):** paste-a-claim; latency/cost pass; 4 adversarial probes; no-fabrication checker; offline mode; deploy to Modal; full eval gate. **Validation:** all gates green; live URL stable.
- **Phase 4 — Ship (D7–D8, Nov 3–4):** video assets + script; README/submission polish; eval re-run; buffer; **submit before Nov 4, 9:00 PM ET.**

## 14. Risks & Mitigations

1. **Library won't freeze (the #1 risk)** → kill rule with floor=4 fires end of D2; decide fast; the library IS the schedule risk.
2. **Muse Code not headless-callable** → codegen port falls back to `pi`, then `llama_direct`; the demo story adjusts honestly ("analysis code authored by an AI coding agent, executed on Modal").
3. **Meta/Modal credentials not ready** → operator checklist D1; offline mode unblocks all build + verify regardless; no lap ever depends on live keys.
4. **Live run stalls on stage** → rehearsed cut to cached notebooks (offline mode), no improvisation.
5. **Cost overrun** → free credits only: frozen images, small max_tokens, cached demo, daily credit checks.

## 15. Operator Checklist (NOT factory issues — laps cannot do these)

- [ ] Create Modal account + token (D1)
- [ ] Put Meta Model API key into the deploy environment (D1)
- [ ] Run `foreman bake qed` VPS-side (instabox snapshot prerequisite, before first lap)
- [ ] Muse Code auth spike: install CLI, verify non-interactive invocation, record the result (D1)
- [ ] Sign off the paper candidate list; make the D2 freeze call (kill rule: floor = 4)
- [ ] Deploy to Modal; verify stable URL
- [ ] Video decision + recording (deferred — deliberately not sliced)
- [ ] Hackathon submission before Nov 4, 9:00 PM ET; keep URL live through Nov 8

## Appendix — Key Dependencies

- Meta Model API (Llama) — reasoning/planning; Meta Muse Code — code authorship (spike-gated); Modal — sandbox execution + deployment
- Reproducibility Project: Psychology (OSF) and Many Labs — primary paper-library sources with recorded replication outcomes
- statsmodels/pandas — re-implementation targets; no licensed statistical software anywhere in the pipeline
