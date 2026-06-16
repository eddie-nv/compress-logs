import streamlit as st
import requests
from pathlib import Path
import tiktoken

# Import crew inline so Streamlit can run without a separate process import.
# The crew module initialises Traceloop on import; keep it lazy to avoid
# crashing when env vars are missing during local development.

COMPRESS_URL = "http://localhost:8000"
SAMPLE_LOGS_DIR = Path("sample_logs")

st.set_page_config(page_title="LogZip — Log Compression Demo", layout="wide")
st.title("LogZip — Log Compression for LLM Agents")
st.caption("Powered by CrewAI + TrueFoundry AI Gateway")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    log_file = st.selectbox(
        "Sample scenario",
        ["ssh_brute_force.log", "api_timeout.log", "k8s_oom.log"],
        help="Choose a log scenario to analyse",
    )
    mode = st.radio(
        "Input mode",
        ["RAW — logs fed directly to agents", "COMPRESSED — through compression layer first"],
        help="Toggle between raw and compressed log paths",
    )
    run_btn = st.button("Run Agents", type="primary", use_container_width=True)

# ── Load log ───────────────────────────────────────────────────────────────
log_path = SAMPLE_LOGS_DIR / log_file
if not log_path.exists():
    st.error(f"Log file not found: {log_path}")
    st.stop()

raw_lines = log_path.read_text().splitlines()
raw_lines = [l for l in raw_lines if l.strip()]

enc = tiktoken.get_encoding("cl100k_base")
raw_text = "\n".join(raw_lines)
raw_token_count = len(enc.encode(raw_text))

# ── Preview columns ────────────────────────────────────────────────────────
col_raw, col_compressed = st.columns(2)

with col_raw:
    st.subheader("Raw logs")
    st.code("\n".join(raw_lines[:30]) + ("\n..." if len(raw_lines) > 30 else ""), language="text")
    st.metric("Lines", len(raw_lines))
    st.metric("Tokens", f"{raw_token_count:,}")

compressed_text = None
if run_btn or True:  # always show compressed preview
    try:
        resp = requests.post(
            f"{COMPRESS_URL}/v1/compress",
            json={"lines": raw_lines},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            compressed_text = data["compressed"]
            with col_compressed:
                st.subheader("Compressed digest")
                st.code(compressed_text, language="text")
                st.metric("Lines (templates)", compressed_text.count("\n") + 1)
                st.metric("Tokens", f"{data['compressed_tokens']:,}")
                st.metric(
                    "Reduction",
                    f"{data['reduction_pct']}%",
                    delta=f"-{data['raw_tokens'] - data['compressed_tokens']:,} tokens",
                    delta_color="inverse",
                )
        else:
            with col_compressed:
                st.warning(f"Compression service returned {resp.status_code}. Is `uvicorn compression.api:app` running?")
    except requests.exceptions.ConnectionError:
        with col_compressed:
            st.warning("Cannot reach compression service on `localhost:8000`. Start it with:\n\n```\nuvicorn compression.api:app --reload\n```")

# ── Agent run ─────────────────────────────────────────────────────────────
if run_btn:
    is_compressed = "COMPRESSED" in mode

    if is_compressed and compressed_text is None:
        st.error("Compression service unavailable — cannot run in compressed mode.")
        st.stop()

    context = compressed_text if is_compressed else raw_text
    tokens_sent = len(enc.encode(context))

    st.divider()
    st.subheader(f"Agent run — {'COMPRESSED' if is_compressed else 'RAW'} mode")
    st.metric("Tokens sent to agents", f"{tokens_sent:,}")

    with st.spinner("CrewAI agents running via TrueFoundry AI Gateway…"):
        try:
            from agents.crew import run_crew
            result = run_crew(context)
            st.success("Crew completed")
            st.markdown(result["output"])
        except Exception as exc:
            st.error(f"Agent run failed: {exc}")
            st.info(
                "Make sure your `.env` file has `TFY_API_KEY`, `TFY_GATEWAY_URL`, "
                "and `TFY_TRACING_ENDPOINT` set."
            )
