# LogZip — Hackathon Scope

**Theme:** Agentic system that works in production  
**Host tech:** CrewAI + TrueFoundry  
**Core idea:** A compression layer that sits between production log streams and LLM agents, so agents spend tokens on reasoning — not on reading 10,000 near-identical error lines.

---

## The Demo

Sample logs → **toggle** → two paths side-by-side:

| | RAW path | COMPRESSED path |
|---|---|---|
| What agents receive | Full raw log text | Compressed digest (`[xN] template [slot summaries]`) |
| Token count | ~12,000 | ~300 |
| Cost | ~$0.37 | ~$0.01 |
| Latency | ~18s | ~2s |
| Agent answer quality | Same or better (less noise) |

The toggle is a Streamlit UI. Both paths run the same 3-agent CrewAI crew. The difference is what context string the crew receives.

---

## Architecture

```
sample_logs/
    ssh_brute_force.log      # ~300 lines, SSH auth flood
    api_timeout.log          # ~300 lines, HTTP 504s + latency variance
    k8s_oom.log              # ~300 lines, OOMKilled restart loop

            │
            ▼
[Streamlit toggle]
            │
    ┌───────┴────────┐
    │ RAW            │ COMPRESSED
    │                │
    │                ▼
    │        FastAPI /v1/compress
    │        (drain3 Python, deployed on TrueFoundry)
    │        → groups repetitive lines into templates
    │        → emits [xN] template [slot summaries]
    │
    └───────┬────────┘
            │
            ▼
    CrewAI Crew (3 agents, all routed via TrueFoundry AI Gateway)
    ├── Triage Agent      → gpt-4o-mini  (cheap, fast)
    ├── Root Cause Agent  → gpt-4o       (accurate)
    └── Remediation Agent → gpt-4o       (accurate)
            │
            ▼
    Incident Report: severity, root cause, fix steps
```

---

## Technology Roles

**Compression layer** (`compression/`)
- Python `drain3` library — same algorithm as `codag-drain` Rust (Drain3, positional similarity)
- Groups repetitive lines into templates with `<*>` wildcards
- Slot summaries: numeric ranges (`[20..8400ms p50=45ms]`), enum values (`[admin,root,ftpuser]`)
- Exposed as a FastAPI microservice (`POST /v1/compress`)
- **No LLM calls** — fully deterministic, sub-millisecond per line

**TrueFoundry**
- Hosts the compression FastAPI service as a deployed microservice
- AI Gateway: routes Triage Agent → `gpt-4o-mini`, Root Cause + Remediation → `gpt-4o`
- Virtual Models (`logdiag/triage`, `logdiag/analysis`) abstract the routing from agent code
- Traceloop SDK integration for live cost/token/latency dashboard

**CrewAI**
- Sequential 3-agent crew: Triage → Root Cause → Remediation
- Each agent passes context forward via `context=[prev_task]`
- Same crew code runs on both raw and compressed paths — only the input string changes

---

## File Structure

```
compress-logs/
├── SCOPE.md                  ← this file
├── README.md
├── requirements.txt
├── .env.example
│
├── sample_logs/
│   ├── ssh_brute_force.log   # scenario 1: SSH auth flood (~300 lines)
│   ├── api_timeout.log       # scenario 2: HTTP 504 cascade (~300 lines)
│   └── k8s_oom.log           # scenario 3: OOMKilled restart loop (~300 lines)
│
├── compression/
│   ├── compressor.py         # drain3 wrapper + [xN] renderer
│   └── api.py                # FastAPI POST /v1/compress
│
├── agents/
│   └── crew.py               # CrewAI 3-agent crew, TrueFoundry LLMs
│
├── demo/
│   └── app.py                # Streamlit toggle UI
│
├── deploy/
│   └── truefoundry.yaml      # TF service + AI Gateway config
│
└── benchmarks/
    └── fetch_loghub.sh       # download LogHub-2.0 OpenSSH subset (back-pocket)
```

---

## Sample Log Scenarios

### `ssh_brute_force.log`
- **Story:** 300 lines from an SSH brute-force attack. ~40 attacker IPs trying `admin`, `root`, `ftpuser`, `pi`, `postgres` repeatedly.
- **Compression:** ~20 unique templates from 300 lines (~15x line, ~8x token)
- **Agent diagnosis:** P1 severity, sshd service, root cause = credential stuffing attack, fix = fail2ban + key-only auth

### `api_timeout.log`
- **Story:** 300 lines from an API gateway log during an incident. `GET /api/v1/users`, `POST /api/v1/orders`, `GET /api/v1/products` all returning 504s with varying latencies (200ms → 30,000ms).
- **Compression:** ~8 unique templates from 300 lines (~38x line, ~12x token)
- **Agent diagnosis:** P1, api-gateway + upstream DB, root cause = DB connection pool exhaustion, fix = scale pool + check slow queries

### `k8s_oom.log`
- **Story:** 300 lines from kubectl across 3 services (payments, orders, inventory). OOMKilled events, pod restarts, memory limit hits on payments-service.
- **Compression:** ~12 unique templates from 300 lines (~25x line, ~10x token)
- **Agent diagnosis:** P2, payments-service, root cause = memory leak / limit too low, fix = increase limit + profile heap

---

## TrueFoundry Setup (from docs)

```python
from crewai import LLM

triage_llm = LLM(
    model="openai/openai-main/gpt-4o-mini",   # or "openai/logdiag/triage" with Virtual Model
    base_url="https://gateway.truefoundry.ai",
    api_key="YOUR_TFY_PAT"
)

analysis_llm = LLM(
    model="openai/openai-main/gpt-4o",         # or "openai/logdiag/analysis"
    base_url="https://gateway.truefoundry.ai",
    api_key="YOUR_TFY_PAT"
)
```

Gateway URL (SaaS): `https://gateway.truefoundry.ai`  
Model format: `openai/<truefoundry-model-id>`  
Virtual Model format: `openai/<group>/<model-name>`

---

## Benchmark Back-Pocket (LogHub-2.0)

The `codag-drain` Rust library benchmarks were run on LogHub-2.0 and achieved:
- **168x line compression** (mean across 14 log systems)
- **40x character compression**
- **0.978 purity** (near-zero false merges)

To run the same numbers with our Python implementation:
```bash
bash benchmarks/fetch_loghub.sh   # downloads OpenSSH_2k.log (~2k labeled lines)
python benchmarks/run_loghub.py   # runs drain3 and prints compression stats
```

Reference: `reference/docs/PUBLIC_BENCHMARKS.md`

---

## What We Are NOT Building

- Live log ingestion from real providers (Vercel, K8s, AWS) — samples only
- Template cache warm/pre-population (codag's moat, not needed for demo)
- Auth, multi-tenancy, billing
- Streaming (batch is fine for demo)
- The Rust codag-drain service (using Python drain3 instead, same algorithm)
