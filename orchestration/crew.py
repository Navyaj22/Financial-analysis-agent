"""Optional CrewAI integration: wraps the Report Writer's LLM call in a CrewAI Agent/Task/Crew.
Returns None (deterministic mode) when no API key or crewai is not installed."""
from __future__ import annotations

from typing import Callable, Optional

from config.settings import Settings


def build_narrator(settings: Settings) -> Optional[Callable[[str], str]]:
    if not settings.llm_enabled:
        return None
    try:
        from crewai import Agent, Crew, LLM, Task
    except ImportError:
        return None

    def narrate(prompt: str) -> str:
        llm = LLM(model=settings.llm_model, api_key=settings.llm_api_key)
        agent = Agent(role="Financial Report Writer",
                      goal="Explain supplied financial facts clearly without inventing information",
                      backstory="A careful research writer who never predicts prices or gives investment advice.",
                      llm=llm, allow_delegation=False, verbose=False)
        task = Task(description=prompt, expected_output="Two short plain-English paragraphs.", agent=agent)
        return str(Crew(agents=[agent], tasks=[task], verbose=False).kickoff())

    return narrate
