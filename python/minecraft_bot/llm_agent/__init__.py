"""LLM-friendly agent wrapper around :class:`~minecraft_bot.bot.Bot`.

This is a *separate*, optional layer on top of the main Bot API.
It exists so an LLM (function-calling capable like Claude / GPT
/ open-weights) can drive a bot via:

- :class:`Toolset` — a registry of callable "tools" with
  JSONSchema-style signatures matching the Anthropic / OpenAI
  function-calling spec.
- :func:`describe_observation` — converts a
  :class:`~minecraft_bot.observation.Observation` into compact
  text + JSON that an LLM can reason over efficiently.
- :func:`run_step` — execute one tool call by name + arguments.

Nothing in the core ``minecraft_bot`` package depends on this — feel
free to drop the directory if you don't need LLM control.
"""

from minecraft_bot.llm_agent.observation_summary import describe_observation
from minecraft_bot.llm_agent.tools import Tool, Toolset, default_toolset, run_step

__all__ = [
    "Tool", "Toolset", "default_toolset", "run_step",
    "describe_observation",
]
