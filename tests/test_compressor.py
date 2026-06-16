import pytest
from pathlib import Path

from compression.compressor import compress, _slot_summary, _try_numeric

SAMPLE_LOGS = Path(__file__).parent.parent / "sample_logs"


# --- _try_numeric ---


def test_try_numeric_returns_none_for_strings():
    assert _try_numeric(["admin", "root"]) is None


def test_try_numeric_returns_single_value_when_all_equal():
    result = _try_numeric(["42ms", "42ms"])
    assert result == "42ms"


def test_try_numeric_returns_range_for_varied_values():
    result = _try_numeric(["10ms", "500ms", "200ms"])
    assert result is not None
    assert "10" in result
    assert "500" in result


def test_try_numeric_handles_bare_floats():
    result = _try_numeric(["1.5", "3.0"])
    assert result is not None
    # 1.5 rounds to 2 with .0f; hi is 3
    assert "2" in result
    assert "3" in result


def test_try_numeric_returns_none_for_empty():
    assert _try_numeric([]) is None


def test_try_numeric_mixed_numeric_and_string_returns_none():
    assert _try_numeric(["10ms", "fast"]) is None


# --- _slot_summary ---


def test_slot_summary_returns_empty_for_no_wildcards():
    result = _slot_summary("Dec 10 sshd: connection closed", ["Dec 10 sshd: connection closed"])
    assert result == ""


def test_slot_summary_returns_enum_for_string_slots():
    template = "sshd: Invalid user <*> from <*>"
    members = [
        "sshd: Invalid user admin from 1.2.3.4",
        "sshd: Invalid user root from 5.6.7.8",
    ]
    result = _slot_summary(template, members)
    assert "admin" in result or "root" in result


def test_slot_summary_returns_numeric_range_for_latency_slots():
    template = "GET /api 200 <*>"
    members = [
        "GET /api 200 10ms",
        "GET /api 200 500ms",
    ]
    result = _slot_summary(template, members)
    assert "10" in result and "500" in result


def test_slot_summary_skips_mismatched_line_lengths():
    template = "sshd <*> closed"
    members = [
        "sshd conn closed",
        "extra token sshd conn closed",  # different token count — should be skipped
    ]
    result = _slot_summary(template, members)
    assert isinstance(result, str)


def test_slot_summary_caps_enum_values_at_six():
    template = "login <*>"
    members = [f"login user{i}" for i in range(10)]
    result = _slot_summary(template, members)
    # Should not have more than 6 unique values piped together
    if result:
        values = result.strip(" []").split("|")
        assert len(values) <= 6


# --- compress ---


def test_compress_returns_tuple_of_three():
    lines = ["Dec 10 sshd: Invalid user admin from 1.2.3.4"] * 3
    result = compress(lines)
    assert len(result) == 3
    text, raw_tok, comp_tok = result
    assert isinstance(text, str)
    assert isinstance(raw_tok, int)
    assert isinstance(comp_tok, int)


def test_compress_empty_lines_returns_empty_text():
    text, raw_tok, comp_tok = compress([])
    assert text == ""
    assert raw_tok == 0
    assert comp_tok == 0


def test_compress_skips_blank_lines():
    lines = ["", "   ", "Dec 10 sshd: closed"]
    text, raw_tok, comp_tok = compress(lines)
    assert text.strip() != ""
    assert "[x1]" in text


def test_compress_groups_identical_lines():
    line = "Dec 10 sshd: Invalid user admin from 1.2.3.4"
    text, _, _ = compress([line] * 5)
    assert "[x5]" in text
    assert text.count("\n") == 0  # single cluster → single line


def test_compress_raw_tokens_greater_than_compressed():
    lines = ["Dec 10 sshd: Invalid user admin from 1.2.3.4"] * 20
    _, raw_tok, comp_tok = compress(lines)
    assert raw_tok > comp_tok


def test_compress_reduction_improves_with_repetition():
    unique_lines = [f"event type={i} value={i*10}" for i in range(50)]
    repeated_lines = ["Dec 10 sshd: Failed password for root from 1.2.3.4"] * 50

    _, raw_u, comp_u = compress(unique_lines)
    _, raw_r, comp_r = compress(repeated_lines)

    reduction_unique = 1 - comp_u / raw_u
    reduction_repeated = 1 - comp_r / raw_r
    assert reduction_repeated > reduction_unique


# --- Integration: sample logs ---


@pytest.mark.parametrize(
    "log_file,max_templates,min_reduction_pct",
    [
        ("ssh_brute_force.log", 60, 30),
        ("api_timeout.log", 20, 80),
        ("k8s_oom.log", 40, 50),
    ],
)
def test_sample_log_compression(log_file, max_templates, min_reduction_pct):
    lines = (SAMPLE_LOGS / log_file).read_text().splitlines(keepends=True)
    text, raw_tok, comp_tok = compress(lines)

    template_count = sum(1 for l in text.splitlines() if l.strip())
    reduction_pct = (1 - comp_tok / raw_tok) * 100 if raw_tok else 0

    assert template_count <= max_templates, (
        f"{log_file}: {template_count} templates > {max_templates} expected"
    )
    assert reduction_pct >= min_reduction_pct, (
        f"{log_file}: {reduction_pct:.1f}% reduction < {min_reduction_pct}% expected"
    )
