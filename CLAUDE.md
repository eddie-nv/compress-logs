# LogZip

Log compression layer for LLM agents — drain3 grouping + FastAPI, CrewAI crew via TrueFoundry AI Gateway.

## Setup

```bash
python3.13 -m venv .venv313
source .venv313/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in TFY_API_KEY and TFY_GATEWAY_URL
```

## Run the demo

```bash
# Start the compression service
uvicorn compression.api:app --reload

# In a second terminal
python demo.py --log ssh_brute_force.log --mode both
```

Flags: `--log [ssh_brute_force.log|api_timeout.log|k8s_oom.log]` · `--mode [raw|compressed|both]`

## Run tests

```bash
python -m pytest tests/ --cov=compression --cov=agents --cov=demo
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
