import os

from dotenv import load_dotenv

load_dotenv()

_traceloop_initialized = False


def _init_traceloop() -> None:
    global _traceloop_initialized
    if _traceloop_initialized:
        return
    endpoint = os.environ.get("TFY_TRACING_ENDPOINT")
    api_key = os.environ.get("TFY_API_KEY")
    if not endpoint or not api_key:
        return
    from traceloop.sdk import Traceloop

    Traceloop.init(
        api_endpoint=endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "TFY-Tracing-Project": os.environ.get(
                "TFY_TRACING_PROJECT", "compress-logs-demo"
            ),
        },
    )
    _traceloop_initialized = True


def run_crew(log_context: str) -> dict:
    from crewai import Agent, Crew, LLM, Task

    gateway = os.environ.get("TFY_GATEWAY_URL")
    api_key = os.environ.get("TFY_API_KEY")
    if not gateway or not api_key:
        raise RuntimeError(
            "TFY_GATEWAY_URL and TFY_API_KEY must be set. "
            "Copy .env.example to .env and fill in your values."
        )

    _init_traceloop()

    triage_llm = LLM(
        model=os.environ.get("TRIAGE_MODEL", "openai/openai-main/gpt-4o-mini"),
        base_url=gateway,
        api_key=api_key,
    )
    analysis_llm = LLM(
        model=os.environ.get("ANALYSIS_MODEL", "openai/openai-main/gpt-4o"),
        base_url=gateway,
        api_key=api_key,
    )

    triage = Agent(
        role="Log Triage Specialist",
        goal="Quickly assess the severity and affected service from log output.",
        backstory=(
            "You are a senior SRE who has triaged thousands of production incidents. "
            "You read logs efficiently and focus on signals, not noise."
        ),
        llm=triage_llm,
        verbose=True,
    )
    root_cause = Agent(
        role="Root Cause Analyst",
        goal="Identify the single most likely root cause of the incident.",
        backstory=(
            "You are a distributed systems expert who excels at tracing cascading "
            "failures back to their origin."
        ),
        llm=analysis_llm,
        verbose=True,
    )
    remediation = Agent(
        role="Remediation Engineer",
        goal="Produce clear, actionable remediation steps to resolve the incident.",
        backstory=(
            "You are an on-call engineer who turns incident root causes into "
            "concrete, prioritized fix steps."
        ),
        llm=analysis_llm,
        verbose=True,
    )

    t1 = Task(
        description=(
            "Triage the following production logs. Identify:\n"
            "1. Severity (P1/P2/P3)\n"
            "2. Affected service(s)\n"
            "3. A 2-sentence error summary\n\n"
            f"LOGS:\n{log_context}"
        ),
        agent=triage,
        expected_output="Severity level, affected service name, and 2-sentence error summary.",
    )
    t2 = Task(
        description=(
            "Based on the triage, identify the single most likely root cause "
            "in 2-3 sentences."
        ),
        agent=root_cause,
        expected_output="Root cause in 2-3 sentences.",
        context=[t1],
    )
    t3 = Task(
        description=(
            "Given the root cause, provide 3-5 numbered remediation steps "
            "to resolve and prevent recurrence."
        ),
        agent=remediation,
        expected_output="Numbered list of 3-5 remediation steps.",
        context=[t2],
    )

    crew = Crew(
        agents=[triage, root_cause, remediation],
        tasks=[t1, t2, t3],
        verbose=True,
    )
    result = crew.kickoff()
    return {"output": str(result)}
