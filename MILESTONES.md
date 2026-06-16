# LogZip — Milestone Plan

Git flow: `feat/<milestone>` branch → commit → push → PR into `main`.

---

## M1 — Compression Engine + API

**Branch:** `feat/m1-compression-engine`

**Goal:** The core deterministic compression pipeline working end-to-end: drain3 grouping, slot summaries, FastAPI wrapper.

**Deliverables:**
- `compression/compressor.py` — `compress(lines) → (text, raw_tokens, compressed_tokens)` with slot summaries (numeric ranges + enum values)
- `compression/api.py` — `POST /v1/compress` returns `{compressed, raw_tokens, compressed_tokens, reduction_pct}`, `GET /health`
- Verified against all 3 sample logs — confirm expected compression ratios:
  - `ssh_brute_force.log` → ~20 templates from 300 lines
  - `api_timeout.log` → ~8 templates from 300 lines
  - `k8s_oom.log` → ~12 templates from 300 lines

**Configs:**
| What | Config |
|---|---|
| Python idioms + type annotations | `python-patterns` skill |
| FastAPI endpoint design | `fastapi-patterns` skill, `/fastapi-review` |
| API contract (request/response shape) | `api-design` skill |
| Error handling in compressor | `error-handling` skill |
| Pytest verification | `python-testing` skill, `/test-coverage` |
| Code review before PR | `/python-review`, `python-reviewer` agent |
| Performance sanity (sub-ms per line) | `performance-optimizer` agent |

---

## M2 — CrewAI Crew + TrueFoundry Gateway

**Branch:** `feat/m2-crewai-crew`

**Goal:** 3-agent sequential crew running through TrueFoundry AI Gateway with Traceloop observability. Both raw and compressed paths verified to produce a valid incident report.

**Deliverables:**
- `agents/crew.py` — `run_crew(log_context) → {"output": str}` with sequential Triage → Root Cause → Remediation
- Triage on `gpt-4o-mini`, Root Cause + Remediation on `gpt-4o`, all via `TFY_GATEWAY_URL`
- Traceloop initialized so cost/latency appears in TrueFoundry dashboard
- Model routing falls back cleanly if `TRIAGE_MODEL`/`ANALYSIS_MODEL` env vars absent
- `.env.example` accurate and complete

**Configs:**
| What | Config |
|---|---|
| CrewAI agent patterns + task chaining | `agentic-engineering` skill |
| Token cost model routing decisions | `cost-aware-llm-pipeline` skill |
| Context budget — what each agent sees | `context-budget` skill |
| ML pipeline review (gateway, tracing) | `mle-workflow` skill, `mle-reviewer` agent |
| Agent architecture review | `architect` agent |
| Code review before PR | `/python-review`, `python-reviewer` agent |

---

## M3 — CLI Demo

**Branch:** `feat/m3-cli-demo`

**Goal:** Replace the Streamlit `demo/app.py` with a proper CLI script at the project root. `python demo.py ssh_brute_force.log --mode both` prints a side-by-side stats table then runs the crew and prints the incident report.

**Deliverables:**
- `demo.py` at project root — `--mode raw|compressed|both`, `--log` flag for log file selection
- Side-by-side table: tokens sent, cost estimate, latency, answer
- `demo/app.py` deleted (Streamlit — explicitly out of scope per SCOPE.md)
- `demo/__init__.py` removed if no longer needed
- Works with compression service running locally on `localhost:8000`
- CLAUDE.md updated to reflect CLI (not Streamlit)

**Configs:**
| What | Config |
|---|---|
| CLI arg parsing patterns | `python-patterns` skill |
| Code review + table output polish | `/python-review`, `/code-review` |
| Final agent review | `python-reviewer` agent |

---

## M4 — TrueFoundry Deploy

**Branch:** `feat/m4-deploy`

**Goal:** Compression service deployable to TrueFoundry with one command. Docker image builds cleanly and serves `/v1/compress` correctly.

**Deliverables:**
- `deploy/Dockerfile` — python:3.11-slim, compression-only deps, `uvicorn compression.api:app`
- `deploy/truefoundry.yaml` — service definition, port 8000, 1 replica, resource limits
- `requirements.txt` split concern documented (Dockerfile installs subset; full file for local dev)
- Manual smoke test: deploy → curl `/health` → curl `/v1/compress` with sample payload

**Configs:**
| What | Config |
|---|---|
| Dockerfile best practices | `docker-patterns` skill |
| Service deployment patterns | `deployment-patterns` skill |
| Architecture review (what to include in image) | `architect` agent |

---

## M5 — Benchmark + Final Review

**Branch:** `feat/m5-benchmark-polish`

**Goal:** Back-pocket LogHub numbers ready for Q&A. End-to-end demo verified clean. Security scan passed.

**Deliverables:**
- `benchmarks/fetch_loghub.sh` — downloads `OpenSSH_2k.log`
- `benchmarks/run_loghub.py` — prints line/char/token compression + purity vs codag-drain reference
- `python demo.py ssh_brute_force.log --mode both` runs cleanly start to finish
- `README.md` written — one-paragraph pitch + setup instructions + demo command
- Security scan clean

**Configs:**
| What | Config |
|---|---|
| Benchmark methodology + metrics | `benchmark` skill, `benchmark-methodology` skill |
| Compression ratio optimization | `benchmark-optimization-loop` skill |
| Performance review | `performance-optimizer` agent |
| Security audit before final PR | `/security-scan`, `security-reviewer` agent |
| Full code review pass | `/code-review`, `code-reviewer` agent |
| Checkpoint before final push | `/checkpoint` |

---

## Summary

| Milestone | Branch | Core Output |
|---|---|---|
| M1 | `feat/m1-compression-engine` | `compression/compressor.py` + `compression/api.py` |
| M2 | `feat/m2-crewai-crew` | `agents/crew.py` + TrueFoundry gateway |
| M3 | `feat/m3-cli-demo` | `demo.py` CLI, Streamlit removed |
| M4 | `feat/m4-deploy` | `deploy/Dockerfile` + `deploy/truefoundry.yaml` |
| M5 | `feat/m5-benchmark-polish` | `benchmarks/` + `README.md` + final review |
