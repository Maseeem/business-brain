import json
import os
import re
from typing import Any

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def _groq_client():
    from groq import Groq
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    return Groq(api_key=key)


def llm_text(system: str, user: str) -> str:
    """Direct Groq fallback used when CrewAI is unavailable or fails."""
    client = _groq_client()
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (response.choices[0].message.content or "").strip()


def _clean_json(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start:end + 1]
    return raw


def crew_json(role: str, goal: str, backstory: str, prompt: str, fallback=None, tools: list[Any] | None = None):
    """Run one real CrewAI agent/task and return parsed JSON.

    The deterministic fallback keeps the app usable when Groq/CrewAI is temporarily unavailable.
    """
    try:
        from crewai import Agent, Crew, LLM, Process, Task
        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is not configured.")
        llm = LLM(model=f"groq/{MODEL}", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
        agent = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            tools=tools or [],
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        task = Task(
            description=prompt,
            expected_output="Only valid JSON. No markdown fences and no commentary.",
            agent=agent,
        )
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        raw = getattr(result, "raw", None) or str(result)
        return json.loads(_clean_json(raw))
    except Exception:
        if fallback is not None:
            return fallback
        raise


def crew_text(role: str, goal: str, backstory: str, prompt: str, fallback=None, tools: list[Any] | None = None) -> str:
    try:
        from crewai import Agent, Crew, LLM, Process, Task
        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is not configured.")
        llm = LLM(model=f"groq/{MODEL}", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
        agent = Agent(role=role, goal=goal, backstory=backstory, tools=tools or [], llm=llm, verbose=False, allow_delegation=False)
        task = Task(description=prompt, expected_output="A concise, user-facing answer.", agent=agent)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()
        return (getattr(result, "raw", None) or str(result)).strip()
    except Exception:
        if fallback is not None:
            return fallback
        raise


def crew_agent(role: str, goal: str, backstory: str, tools: list[Any] | None = None):
    from crewai import Agent, LLM
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is not configured.")
    llm = LLM(model=f"groq/{MODEL}", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
    return Agent(role=role, goal=goal, backstory=backstory, tools=tools or [], llm=llm, verbose=False, allow_delegation=False)
