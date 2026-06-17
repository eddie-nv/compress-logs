import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from demo import _table, estimate_cost, load_log


# --- estimate_cost ---


def test_estimate_cost_zero_tokens():
    assert estimate_cost(0) == 0.0


def test_estimate_cost_scales_with_tokens():
    cost_1k = estimate_cost(1_000)
    cost_10k = estimate_cost(10_000)
    assert cost_10k == pytest.approx(cost_1k * 10)


def test_estimate_cost_compressed_cheaper_than_raw():
    # typical ratio from our sample logs
    raw_cost = estimate_cost(8_000)
    comp_cost = estimate_cost(800)
    assert comp_cost < raw_cost


# --- _table ---


def test_table_contains_header():
    result = _table(("A", "B", "C"), [("1", "2", "3")])
    assert "A" in result and "B" in result and "C" in result


def test_table_contains_row_values():
    result = _table(("H1", "H2", "H3"), [("foo", "bar", "baz")])
    assert "foo" in result
    assert "bar" in result
    assert "baz" in result


def test_table_has_separator_lines():
    result = _table(("A", "B", "C"), [("x", "y", "z")])
    assert "+" in result and "-" in result


def test_table_three_rows():
    rows = [("a", "b", "c"), ("d", "e", "f"), ("g", "h", "i")]
    result = _table(("H1", "H2", "H3"), rows)
    for cell in ["a", "b", "c", "d", "e", "f", "g", "h", "i"]:
        assert cell in result


# --- load_log ---


def test_load_log_ssh_brute_force():
    lines, text = load_log("ssh_brute_force.log")
    assert len(lines) > 0
    assert all(l.strip() for l in lines)
    assert "\n".join(lines) == text


def test_load_log_api_timeout():
    lines, text = load_log("api_timeout.log")
    assert len(lines) > 0


def test_load_log_k8s_oom():
    lines, text = load_log("k8s_oom.log")
    assert len(lines) > 0


def test_load_log_missing_file_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        load_log("nonexistent.log")
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "nonexistent.log" in captured.err
    assert "Available" in captured.err


# --- compress ---


def test_compress_calls_correct_endpoint():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "compressed": "[x5] sshd: Invalid user <*>  [admin|root]",
        "raw_tokens": 500,
        "compressed_tokens": 20,
        "reduction_pct": 96.0,
    }
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        from demo import compress
        result = compress(["line1", "line2"])
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "/v1/compress" in call_kwargs.args[0]
        assert result["reduction_pct"] == 96.0


def test_compress_connection_error_exits(capsys):
    import httpx as _httpx
    with patch("httpx.post", side_effect=_httpx.ConnectError("refused")):
        from demo import compress
        with pytest.raises(SystemExit) as exc:
            compress(["line"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "localhost:8000" in captured.err


# --- main: integration (mocked) ---


def test_main_both_mode_calls_compress_and_crew(capsys):
    comp_payload = {
        "compressed": "[x5] template  [admin|root]",
        "raw_tokens": 1000,
        "compressed_tokens": 50,
        "reduction_pct": 95.0,
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = comp_payload

    with (
        patch("httpx.post", return_value=mock_resp),
        patch("agents.crew.run_crew", return_value={"output": "P1: DB issue. Fix: scale pool."}),
        patch("sys.argv", ["demo.py", "--log", "ssh_brute_force.log", "--mode", "both"]),
    ):
        from demo import main
        main()

    captured = capsys.readouterr()
    assert "Tokens sent to agents" in captured.out
    assert "Incident Report" in captured.out


def test_main_compressed_mode_skips_table(capsys):
    comp_payload = {
        "compressed": "[x10] template",
        "raw_tokens": 800,
        "compressed_tokens": 40,
        "reduction_pct": 95.0,
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = comp_payload

    with (
        patch("httpx.post", return_value=mock_resp),
        patch("agents.crew.run_crew", return_value={"output": "P2: OOM on payments."}),
        patch("sys.argv", ["demo.py", "--mode", "compressed"]),
    ):
        from demo import main
        main()

    captured = capsys.readouterr()
    assert "Tokens sent to agents" not in captured.out
    assert "Incident Report" in captured.out


def test_main_raw_mode_skips_compression(capsys):
    with (
        patch("httpx.post") as mock_post,
        patch("agents.crew.run_crew", return_value={"output": "P1: SSH brute force."}),
        patch("sys.argv", ["demo.py", "--mode", "raw"]),
    ):
        from demo import main
        main()

    mock_post.assert_not_called()
    captured = capsys.readouterr()
    assert "Incident Report" in captured.out
