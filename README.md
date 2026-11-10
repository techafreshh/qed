# QED

*A second opinion for published science.*

QED takes a published paper's headline claim plus its public replication package, writes its own analysis code from scratch (the authors' scripts are never executed), runs that code in a sandbox, and returns a verdict — `REPLICATED` / `PARTIAL` / `FAILED` — with the executed notebook as the receipt. Every number on the verdict card traces to an executed cell output.

## Why it exists

Reproduction packages too often go unrun: environment drift, missing data pins, or silent reliance on the authors' own scripts make "reproducible" hard to check. QED redoes the headline analysis independently — plan, code, execute, compare against a deterministic rubric (`rubric/verdict.py`) — so a reader can trust the verdict without trusting the model that wrote the code. The product requirements live in [`.agents/PRDs/PRD.md`](.agents/PRDs/PRD.md).

## Quickstart

Requires Python 3.12+.

```sh
git clone https://github.com/techafreshh/qed.git
cd qed
pip install -r requirements.txt
cp .env.example .env   # fill in META_API_KEY / MODAL_TOKEN for live runs; never commit .env
```

Run the service:

```sh
make dev   # uvicorn app.main:app on http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000` for the UI, or check the service is up:

```sh
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/papers
```

> [!TIP]
> No API keys? Stay on the offline path — it's the default (`QED_OFFLINE=1` in `.env.example`), serves the demo papers with zero egress and zero spend, and every gate below exits 0 without credentials:
>
> ```sh
> QED_OFFLINE=1 make test && make replay && make eval
> ```

Paste-a-claim against the offline demo (service running via `make dev` or `make demo-offline`):

```sh
curl -X POST http://127.0.0.1:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"paper_id":"demo_replicated","claim":"wages rise"}'
curl -X POST http://127.0.0.1:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"paper_id":"demo_failed","claim":"wages rise"}'
```

To serve the offline demo UI directly:

```sh
make demo-offline   # QED_OFFLINE=1 uvicorn app.main:app on :8000
```

## Usage

### REST API

| Method & path | Purpose |
| --- | --- |
| `GET /health` | Liveness probe (`{"ok": true}`) |
| `GET /api/papers` | List the frozen paper library |
| `POST /api/runs` | Queue a run: `{"paper_id": "...", "claim": "...", "paper_text": "..."}` (all but `paper_text` required, non-blank; vague claims are rejected with 422). Returns `202 {"run_id", "status"}` |
| `GET /api/runs/{id}` | Run detail, including the verdict card when complete |
| `GET /api/runs/{id}/notebook` | Executed notebook cells (the receipt behind the verdict; `409` while the run is still queued/running) |
| `GET /api/runs/{id}/events` | SSE trace of the run (AG-UI event stream consumed by the side-chat panel) |

The full acceptance probe chain is `GET /health → GET /api/papers → POST /api/runs → GET /api/runs/{id} → GET /api/runs/{id}/notebook → GET /api/runs/{id}/events` (200/200/202/200/200/200 for a completed run); `scripts/demo_offline.py` drives it credential-free under `QED_OFFLINE=1`. A `GET /` serves the UI bundle and any unknown path falls back to the SPA shell.

### Offline demo papers

With `QED_OFFLINE=1`, runs for the demo ids replay from the cache in `library/cache/` (`runner/offline.py`) instead of calling any model or sandbox:

- `demo_replicated` — replays to `REPLICATED`
- `demo_failed` — replays to `FAILED`

### Gates

```sh
make test          # full suite (credential-free): python3 -m pytest -q
make replay        # frozen-library replay parity: QED_OFFLINE=1 python3 evals/replay.py
make eval          # full offline eval gate (replay + adversarial probes + no-fabrication checks)
make build-ui      # rebuild the UI bundle into app/static/index.html (needs npm; otherwise the checked-in fallback bundle is used)
```

### Deploy

```sh
modal deploy modal_app.py   # serve app.main:app (UI bundle included) at the stable `qed` app URL
modal serve modal_app.py    # preview without deploying
```

`modal_app.py` imports `modal` lazily, so offline tests and replay never touch it; the live sandbox path (`runner/sandbox.py:run_code`) needs `MODAL_TOKEN`.

## Configuration

All settings come from the environment (see [`.env.example`](.env.example)); secrets are never logged. Copy `.env.example` to `.env` and never commit `.env`.

| Variable | Default | Effect |
| --- | --- | --- |
| `QED_OFFLINE` | `1` (on) | Offline-first: unset or empty means offline; only an explicit `0` / `false` / `no` / `off` opts out (`app/config.py:parse_offline`). Offline serves cached demo verdicts and deterministic stubs instead of calling models or sandboxes. |
| `QED_CODEGEN_BACKEND` | `llama_direct` | Analysis-code author port (`codegen/factory.py`): `muse` / `pi` / `llama_direct`. |
| `QED_MUSE_MODEL` | `muse-spark-1.3-contributor` | Model invoked headlessly via the `pi` CLI by the Muse backend (`codegen/muse_backend.py`). |
| `META_API_KEY` | _(empty)_ | Key for the Meta Model API (Llama reasoning, planning, verdict narration in `agent/llm.py`; Llama codegen in `codegen/llama_backend.py`). Empty means the deterministic offline stubs stand in. |
| `META_API_URL` | `https://api.llama.com/v1/chat/completions` | Override for the Meta Model API endpoint (`agent/llm.py`, `codegen/llama_backend.py`). |
| `MODAL_TOKEN` | _(empty)_ | Token for Modal sandboxed execution and `modal deploy` (`app/config.py`, `modal_app.py`). |

## The paper library

QED validates against a frozen library of pre-vetted papers; each manifest pins its dataset URL + sha256 + license, estimator spec, and reported numbers (`library/papers/*.yaml`, validated by `library/schema.py:load_library`). QED writes its own analysis code against the public replication package — it never executes the authors' scripts.

| paper | expected verdict | source |
| --- | --- | --- |
| Card & Krueger (1994), minimum wage | `REPLICATED` | original Table 3, pinned CSV mirror |
| Hsee (1998) less-is-better via Many Labs 2 | `REPLICATED` | Klein et al. (2018), Many Labs 2 |
| Zhong & Liljenquist (2006) Macbeth via Many Labs 2 | `FAILED` | failed replication, Klein et al. (2018) |
| Reinhart & Rogoff (2010) debt, Herndon-Ash-Pollin correction | `PARTIAL` | Herndon, Ash & Pollin (2013) |

Verdicts come from the deterministic coded rubric — the rubric decides, the model explains (`rubric/verdict.py`: `REPLICATED` / `PARTIAL` / `FAILED`). (`library/papers/example.yaml` is a placeholder fixture, not a validation paper.)

## Architecture

Short map for navigating the tree:

- `app/` — FastAPI service (`main.py` routes, `api/` endpoints, `config.py` settings, `worker.py` run scheduling); UI bundle served from `app/static/`
- `agent/` — orchestration: claim extraction, spec-grid planning, failure diagnosis, verdict narration (`llm.py` holds the Meta Model API client)
- `codegen/` — pluggable code-author port: `muse` / `pi` / `llama_direct` backends plus `factory.py` selection
- `runner/` — sandboxed execution (`sandbox.py` Modal path, `offline.py` cached replay, `notebook.py` cell runner)
- `rubric/` — deterministic verdict functions (pure stdlib, no network)
- `library/papers/` — frozen paper manifests; `library/cache/` — offline replay fixtures
- `evals/`, `scripts/` — replay, adversarial probes, and no-fabrication gates (also runnable as documentation)
- `ui/` — React + Vite front end (CopilotKit side-chat over the AG-UI event stream, with a REST fallback)
- `modal_app.py` — Modal deployment entrypoint for the same FastAPI app

## Limitations

- **Offline stubs stand in without keys.** With `QED_OFFLINE=1` (the default) or no `META_API_KEY`, planning/narration return deterministic `stub:…` strings and demo runs replay cached verdicts — useful for evaluation, not live science.
- **The Muse path needs the `pi` CLI.** Without the `pi` binary (or while offline), the Muse backend returns a marked deterministic template instead of model-authored code.
- **Live execution needs `MODAL_TOKEN`.** Without it, runs stay on the offline/cached path; only the Modal sandbox runs untrusted code in locked-down images.
- **Execution is time-boxed.** Notebook cells run with a hard cap (`MAX_TIMEOUT_S = 300.0` in `runner/notebook.py`); long-running analyses are cut off.
- **Small frozen validation library.** Four papers plus a placeholder fixture — broad enough for the demo and replay gates, not a survey of the literature.
- **Vague claims are refused.** `POST /api/runs` returns 422 for blank or underspecified (non-falsifiable) claims rather than queueing a run.

MIT — see [LICENSE](LICENSE).
