import importlib
import os
from unittest.mock import MagicMock, call, patch

import pytest


BASE_ENV = {
    "TFY_GATEWAY_URL": "https://gateway.truefoundry.ai",
    "TFY_API_KEY": "test-key",
}


@pytest.fixture(autouse=True)
def reset_traceloop_flag():
    """Ensure Traceloop init flag is reset between tests."""
    import agents.crew as crew_module

    crew_module._traceloop_initialized = False
    yield
    crew_module._traceloop_initialized = False


# --- run_crew: env var validation ---


def test_run_crew_raises_when_gateway_missing():
    with patch.dict(os.environ, {"TFY_API_KEY": "key"}, clear=True):
        os.environ.pop("TFY_GATEWAY_URL", None)
        from agents.crew import run_crew

        with pytest.raises(RuntimeError, match="TFY_GATEWAY_URL"):
            run_crew("some logs")


def test_run_crew_raises_when_api_key_missing():
    with patch.dict(os.environ, {"TFY_GATEWAY_URL": "https://gw"}, clear=True):
        os.environ.pop("TFY_API_KEY", None)
        from agents.crew import run_crew

        with pytest.raises(RuntimeError, match="TFY_API_KEY"):
            run_crew("some logs")


# --- run_crew: model routing ---


def test_run_crew_uses_default_triage_model(mock_crewai):
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from agents.crew import run_crew

        run_crew("log line")
        llm_calls = mock_crewai["LLM"].call_args_list
        triage_call = llm_calls[0]
        assert triage_call.kwargs["model"] == "openai/openai-main/gpt-4o-mini"


def test_run_crew_uses_default_analysis_model(mock_crewai):
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from agents.crew import run_crew

        run_crew("log line")
        llm_calls = mock_crewai["LLM"].call_args_list
        analysis_call = llm_calls[1]
        assert analysis_call.kwargs["model"] == "openai/openai-main/gpt-4o"


def test_run_crew_respects_triage_model_env_var(mock_crewai):
    env = {**BASE_ENV, "TRIAGE_MODEL": "openai/logdiag/triage"}
    with patch.dict(os.environ, env, clear=True):
        from agents.crew import run_crew

        run_crew("log line")
        triage_call = mock_crewai["LLM"].call_args_list[0]
        assert triage_call.kwargs["model"] == "openai/logdiag/triage"


def test_run_crew_respects_analysis_model_env_var(mock_crewai):
    env = {**BASE_ENV, "ANALYSIS_MODEL": "openai/logdiag/analysis"}
    with patch.dict(os.environ, env, clear=True):
        from agents.crew import run_crew

        run_crew("log line")
        analysis_call = mock_crewai["LLM"].call_args_list[1]
        assert analysis_call.kwargs["model"] == "openai/logdiag/analysis"


def test_run_crew_passes_gateway_to_llm(mock_crewai):
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from agents.crew import run_crew

        run_crew("log line")
        for llm_call in mock_crewai["LLM"].call_args_list:
            assert llm_call.kwargs["base_url"] == BASE_ENV["TFY_GATEWAY_URL"]


# --- run_crew: output shape ---


def test_run_crew_returns_dict_with_output_key(mock_crewai):
    mock_crewai["crew_instance"].kickoff.return_value = "incident report"
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from agents.crew import run_crew

        result = run_crew("log line")
        assert isinstance(result, dict)
        assert "output" in result


def test_run_crew_output_is_string(mock_crewai):
    mock_crewai["crew_instance"].kickoff.return_value = "some crew output"
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from agents.crew import run_crew

        result = run_crew("log line")
        assert isinstance(result["output"], str)


def test_run_crew_log_context_appears_in_triage_task(mock_crewai):
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from agents.crew import run_crew

        run_crew("CRITICAL: disk full on worker-3")
        task_calls = mock_crewai["Task"].call_args_list
        triage_description = task_calls[0].kwargs["description"]
        assert "CRITICAL: disk full on worker-3" in triage_description


# --- Traceloop initialization ---


def test_traceloop_not_called_without_endpoint(mock_crewai):
    env = {**BASE_ENV}
    env.pop("TFY_TRACING_ENDPOINT", None)
    with patch.dict(os.environ, env, clear=True):
        with patch("agents.crew._init_traceloop") as mock_init:
            from agents.crew import run_crew

            run_crew("log line")
            mock_init.assert_called_once()


def test_traceloop_init_called_with_endpoint(mock_crewai):
    env = {
        **BASE_ENV,
        "TFY_TRACING_ENDPOINT": "https://gateway.truefoundry.ai/api/tracing",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("traceloop.sdk.Traceloop.init") as mock_tl:
            from agents.crew import run_crew

            run_crew("log line")
            mock_tl.assert_called_once()
            init_kwargs = mock_tl.call_args.kwargs
            assert init_kwargs["api_endpoint"] == env["TFY_TRACING_ENDPOINT"]


def test_traceloop_init_not_called_twice(mock_crewai):
    env = {
        **BASE_ENV,
        "TFY_TRACING_ENDPOINT": "https://gateway.truefoundry.ai/api/tracing",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("traceloop.sdk.Traceloop.init") as mock_tl:
            from agents.crew import run_crew

            run_crew("log line")
            run_crew("log line again")
            assert mock_tl.call_count == 1


# --- crew structure ---


def test_crew_has_three_agents(mock_crewai):
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from agents.crew import run_crew

        run_crew("log line")
        crew_kwargs = mock_crewai["Crew"].call_args.kwargs
        assert len(crew_kwargs["agents"]) == 3


def test_crew_has_three_tasks(mock_crewai):
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from agents.crew import run_crew

        run_crew("log line")
        crew_kwargs = mock_crewai["Crew"].call_args.kwargs
        assert len(crew_kwargs["tasks"]) == 3


# --- fixtures ---


@pytest.fixture
def mock_crewai():
    crew_instance = MagicMock()
    crew_instance.kickoff.return_value = "P1 incident: DB connection pool exhausted."

    with (
        patch("crewai.LLM") as mock_llm,
        patch("crewai.Agent") as mock_agent,
        patch("crewai.Task") as mock_task,
        patch("crewai.Crew", return_value=crew_instance) as mock_crew,
    ):
        yield {
            "LLM": mock_llm,
            "Agent": mock_agent,
            "Task": mock_task,
            "Crew": mock_crew,
            "crew_instance": crew_instance,
        }
