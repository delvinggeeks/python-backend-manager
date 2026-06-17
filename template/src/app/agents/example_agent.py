"""Framework-agnostic agent runner.

The base template ships no agent framework. A project enables exactly one via
its extra (`pydantic-ai`, `langgraph`, or `openai-agents`) plus the `llm` extra.

This module resolves the model tier from settings (the deterministic -> RAG ->
frontier cascade lives at the call site) and runs a prompt against whichever
framework is installed, degrading to the raw Anthropic client, then to a clear
error if nothing is available. Imports are lazy so missing extras never break
app startup.
"""

from __future__ import annotations

from importlib.util import find_spec

from app.core.config import get_settings


class AgentUnavailableError(RuntimeError):
    """Raised when no agent backend or API key is configured."""


def resolve_model(tier: str) -> str:
    s = get_settings()
    return {"fast": s.model_fast, "frontier": s.model_frontier}.get(tier, s.model_default)


async def run_agent(prompt: str, tier: str = "default") -> tuple[str, str]:
    """Return (output_text, model_used). Picks the installed backend."""
    settings = get_settings()
    model = resolve_model(tier)

    if not settings.anthropic_api_key:
        raise AgentUnavailableError(
            "ANTHROPIC_API_KEY is not set. Add it to .env, or install an agent "
            "framework extra (e.g. `uv sync --extra llm --extra pydantic-ai`)."
        )

    # Preferred path: pydantic-ai (typed, lightweight, pydantic-native).
    if find_spec("pydantic_ai") is not None:
        from pydantic_ai import Agent  # type: ignore[import-not-found, unused-ignore]

        agent: Agent[None, str] = Agent(f"anthropic:{model}")
        result = await agent.run(prompt)
        return result.output, model

    # Fallback: raw Anthropic SDK (installed via the `llm` extra).
    if find_spec("anthropic") is not None:
        from anthropic import AsyncAnthropic  # type: ignore[import-not-found, unused-ignore]

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if block.type == "text")
        return text, model

    raise AgentUnavailableError(
        "No agent backend installed. Run: "
        "`uv sync --extra llm` (raw client) or `--extra pydantic-ai` (framework)."
    )
