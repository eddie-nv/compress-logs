"""
Back-pocket benchmark: run drain3 on LogHub-2.0 OpenSSH subset and print
compression stats comparable to the codag-drain published numbers.

Usage:
    bash benchmarks/fetch_loghub.sh
    python benchmarks/run_loghub.py
"""
import csv
import sys
from pathlib import Path
from collections import defaultdict

try:
    from drain3 import TemplateMiner
    from drain3.template_miner_config import TemplateMinerConfig
    import tiktoken
except ImportError:
    sys.exit("Run: pip install drain3 tiktoken")

LOG_FILE = Path("benchmarks/loghub/OpenSSH_2k.log")
STRUCT_FILE = Path("benchmarks/loghub/OpenSSH_2k.log_structured.csv")

if not LOG_FILE.exists():
    sys.exit(f"Missing {LOG_FILE}. Run: bash benchmarks/fetch_loghub.sh")


def load_ground_truth(struct_file: Path) -> dict[int, str]:
    """Returns {line_number: EventId} from the structured CSV."""
    gt = {}
    if not struct_file.exists():
        return gt
    with open(struct_file, newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            gt[i] = row.get("EventId", "")
    return gt


def main():
    lines = LOG_FILE.read_text().splitlines()
    lines = [l for l in lines if l.strip()]
    print(f"Loaded {len(lines)} log lines from {LOG_FILE}")

    config = TemplateMinerConfig()
    config.drain_sim_th = 0.4
    config.drain_depth = 4
    config.drain_max_children = 100
    miner = TemplateMiner(config=config)

    cluster_lines: dict[int, list[str]] = defaultdict(list)
    for line in lines:
        result = miner.add_log_message(line)
        cluster_lines[result["cluster_id"]].append(line)

    enc = tiktoken.get_encoding("cl100k_base")

    raw_tokens = sum(len(enc.encode(l)) for l in lines)
    compressed_parts = []
    for cid, members in cluster_lines.items():
        cluster = miner.drain.id_to_cluster[cid]
        template = " ".join(cluster.log_template_tokens)
        compressed_parts.append(f"[x{len(members)}] {template}")
    compressed = "\n".join(compressed_parts)
    comp_tokens = len(enc.encode(compressed))

    n_templates = len(cluster_lines)
    line_cx = len(lines) / n_templates if n_templates else 0
    char_cx = sum(len(l) for l in lines) / max(len(compressed), 1)
    token_cx = raw_tokens / max(comp_tokens, 1)

    # Purity: fraction of lines whose assigned template matches ground truth EventId
    gt = load_ground_truth(STRUCT_FILE)
    if gt:
        cluster_gt: dict[int, list[str]] = defaultdict(list)
        for i, line in enumerate(lines, start=1):
            result = miner.match(line)
            cid = result.cluster_id if result else -1
            cluster_gt[cid].append(gt.get(i, ""))

        correct = 0
        for cid, event_ids in cluster_gt.items():
            if not event_ids:
                continue
            majority = max(set(event_ids), key=event_ids.count)
            correct += event_ids.count(majority)
        purity = correct / len(lines)
    else:
        purity = None

    print()
    print("=" * 50)
    print("LogHub-2.0 OpenSSH benchmark (Python drain3)")
    print("=" * 50)
    print(f"  Lines:             {len(lines):>8,}")
    print(f"  Templates found:   {n_templates:>8,}")
    print(f"  Line compression:  {line_cx:>8.1f}x")
    print(f"  Char compression:  {char_cx:>8.1f}x")
    print(f"  Token compression: {token_cx:>8.1f}x")
    print(f"  Raw tokens:        {raw_tokens:>8,}")
    print(f"  Compressed tokens: {comp_tokens:>8,}")
    print(f"  Token reduction:   {(1 - comp_tokens/raw_tokens)*100:>7.1f}%")
    if purity is not None:
        print(f"  Purity:            {purity:>8.3f}")
    print()
    print("Reference (codag-drain Rust on LogHub-2.0 full):")
    print("  Line compression:   168x mean")
    print("  Char compression:    40x mean")
    print("  Purity:           0.978 mean")
    print("=" * 50)


if __name__ == "__main__":
    main()
