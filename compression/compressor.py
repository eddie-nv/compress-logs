from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from collections import defaultdict
import tiktoken


def compress(lines: list[str]) -> tuple[str, int, int]:
    """
    Groups repetitive log lines using the Drain algorithm and renders each
    cluster as [xN] <template> with slot summaries for numeric fields.

    Returns (compressed_text, raw_token_count, compressed_token_count).
    """
    config = TemplateMinerConfig()
    config.drain_sim_th = 0.4
    config.drain_depth = 4
    config.drain_max_children = 100
    miner = TemplateMiner(config=config)

    cluster_lines: dict[int, list[str]] = defaultdict(list)
    for line in lines:
        if not line.strip():
            continue
        result = miner.add_log_message(line)
        cluster_lines[result["cluster_id"]].append(line)

    enc = tiktoken.get_encoding("cl100k_base")
    raw_tokens = sum(len(enc.encode(l)) for l in lines)

    parts = []
    for cluster_id, members in cluster_lines.items():
        cluster = miner.drain.id_to_cluster[cluster_id]
        template = " ".join(cluster.log_template_tokens)
        slot_summary = _slot_summary(template, members)
        parts.append(f"[x{len(members)}] {template}{slot_summary}")

    compressed = "\n".join(parts)
    compressed_tokens = len(enc.encode(compressed))
    return compressed, raw_tokens, compressed_tokens


def _slot_summary(template: str, members: list[str]) -> str:
    """Appends a human-readable slot summary for wildcard positions."""
    tokens = template.split()
    wildcard_positions = [i for i, t in enumerate(tokens) if t == "<*>"]
    if not wildcard_positions:
        return ""

    slot_values: dict[int, list[str]] = defaultdict(list)
    for line in members:
        line_tokens = line.split()
        if len(line_tokens) != len(tokens):
            continue
        for pos in wildcard_positions:
            slot_values[pos].append(line_tokens[pos])

    summaries = []
    for pos in wildcard_positions:
        vals = slot_values.get(pos, [])
        if not vals:
            continue
        numeric = _try_numeric(vals)
        if numeric:
            summaries.append(numeric)
        else:
            unique = list(dict.fromkeys(vals))[:6]
            summaries.append("|".join(unique))

    if summaries:
        return "  [" + ", ".join(summaries) + "]"
    return ""


def _try_numeric(vals: list[str]) -> str | None:
    """Returns min/max summary if all values parse as numbers, else None."""
    nums = []
    for v in vals:
        stripped = v.rstrip("ms%MiGiBKb")
        try:
            nums.append(float(stripped))
        except ValueError:
            return None
    if not nums:
        return None
    lo, hi = min(nums), max(nums)
    if lo == hi:
        return f"{vals[0]}"
    return f"{vals[0].rstrip('0123456789.')}[{lo:.0f}..{hi:.0f}]"
