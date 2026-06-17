# LogZip

LogZip is a log compression layer for LLM agents: it groups thousands of near-identical log lines into a compact digest using the Drain algorithm, then feeds that digest to a three-agent CrewAI crew (Triage → Root Cause → Remediation) via TrueFoundry AI Gateway — cutting input tokens by 90 %+ and agent cost by a matching factor while preserving the signal needed for accurate incident analysis.

## Setup

```bash
python3.13 -m venv .venv313
source .venv313/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in TFY_API_KEY and TFY_GATEWAY_URL
```

## Run the demo

```bash
# Terminal 1 — start the compression service
uvicorn compression.api:app --reload

# Terminal 2 — side-by-side comparison + crew run
python demo.py --log ssh_brute_force.log --mode both
```

Flags: `--log [ssh_brute_force.log|api_timeout.log|k8s_oom.log]` · `--mode [raw|compressed|both]`

## Run tests

```bash
python -m pytest tests/ --cov=compression --cov=agents --cov=demo
```

## Benchmark

```bash
bash benchmarks/fetch_loghub.sh   # downloads OpenSSH_2k.log from LogHub-2.0
python benchmarks/run_loghub.py   # prints token compression + purity vs codag-drain reference
```

## Deploy

```bash
pip install truefoundry
tfy login
tfy deploy --file deploy/truefoundry.yaml
```

## Project layout

```
compression/   drain3 compressor + FastAPI service
agents/        CrewAI 3-agent crew (Triage → Root Cause → Remediation)
demo.py        CLI demo — side-by-side comparison + crew run
deploy/        Dockerfile + TrueFoundry service config
benchmarks/    LogHub-2.0 benchmark scripts
sample_logs/   SSH brute force, API 504 cascade, K8s OOM scenarios
```
