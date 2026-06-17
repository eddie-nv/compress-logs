#!/usr/bin/env python3
"""
LogZip CLI demo.

Usage:
    python demo.py [--log <file>] [--mode raw|compressed|both]
"""
import argparse
import sys
import time
from pathlib import Path

import httpx
import tiktoken

COMPRESS_URL = "http://localhost:8000"
SAMPLE_LOGS_DIR = Path(__file__).parent / "sample_logs"

# Pricing per 1M input tokens (June 2025 rates)
_MINI_INPUT_PER_M = 0.15   # gpt-4o-mini (triage agent)
_GPT4O_INPUT_PER_M = 5.00  # gpt-4o (root-cause + remediation agents)


def estimate_cost(tokens: int) -> float:
    """Rough input-token cost: 1 triage agent (mini) + 2 analysis agents (gpt-4o)."""
    return (tokens / 1_000_000) * (_MINI_INPUT_PER_M + _GPT4O_INPUT_PER_M * 2)


def load_log(log_file: str) -> tuple[list[str], str]:
    path = SAMPLE_LOGS_DIR / log_file
    if not path.exists():
        available = sorted(f.name for f in SAMPLE_LOGS_DIR.glob("*.log"))
        print(f"Error: '{log_file}' not found. Available: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return lines, "\n".join(lines)


def compress(lines: list[str]) -> dict:
    try:
        resp = httpx.post(f"{COMPRESS_URL}/v1/compress", json={"lines": lines}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(
            "Error: Cannot reach compression service on localhost:8000.\n"
            "Start it with:  uvicorn compression.api:app --reload",
            file=sys.stderr,
        )
        sys.exit(1)


def run_agents(context: str) -> tuple[str, float]:
    from agents.crew import run_crew

    start = time.perf_counter()
    result = run_crew(context)
    return result["output"], time.perf_counter() - start


def _table(header: tuple[str, str, str], rows: list[tuple[str, str, str]]) -> str:
    widths = [
        max(len(header[i]), *(len(r[i]) for r in rows))
        for i in range(3)
    ]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in widths) + " |"
    lines = [sep, fmt.format(*header), sep, *(fmt.format(*r) for r in rows), sep]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="LogZip CLI demo")
    parser.add_argument(
        "--log", "-l",
        default="ssh_brute_force.log",
        metavar="FILE",
        help="Log file from sample_logs/ (default: ssh_brute_force.log)",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["raw", "compressed", "both"],
        default="both",
        help="Which path(s) to run (default: both)",
    )
    args = parser.parse_args()

    lines, raw_text = load_log(args.log)
    enc = tiktoken.get_encoding("cl100k_base")
    raw_tokens = len(enc.encode(raw_text))

    print(f"\nLogZip  ·  {args.log}  ·  {len(lines)} lines  ·  {raw_tokens:,} raw tokens\n")

    comp_text: str | None = None
    comp_tokens: int | None = None

    if args.mode in ("compressed", "both"):
        print("Compressing…")
        data = compress(lines)
        comp_text = data["compressed"]
        comp_tokens = data["compressed_tokens"]
        reduction = data["reduction_pct"]

    if args.mode == "both":
        assert comp_tokens is not None
        raw_cost = estimate_cost(raw_tokens)
        comp_cost = estimate_cost(comp_tokens)
        savings_pct = round((raw_cost - comp_cost) / raw_cost * 100)

        print()
        print(_table(
            header=("Metric", "RAW path", "COMPRESSED path"),
            rows=[
                ("Tokens sent to agents", f"{raw_tokens:,}", f"{comp_tokens:,}"),
                ("Token reduction",       "—",               f"{reduction}%"),
                ("Est. input cost",       f"${raw_cost:.4f}", f"${comp_cost:.4f}"),
                ("Cost savings",          "—",               f"{savings_pct}%"),
            ],
        ))
        print()
        context = comp_text
    elif args.mode == "compressed":
        context = comp_text
    else:
        context = raw_text

    assert context is not None
    tokens_sent = len(enc.encode(context))
    print(f"Running crew on {args.mode} path  ·  {tokens_sent:,} tokens  ·  est. ${estimate_cost(tokens_sent):.4f}\n")

    output, elapsed = run_agents(context)

    print(f"─── Incident Report  ({elapsed:.1f}s) ───\n")
    print(output)
    print()


if __name__ == "__main__":
    main()
