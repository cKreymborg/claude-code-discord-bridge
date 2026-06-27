"""Per-element display configuration for what ccdb posts to Discord.

The final assistant answer is always shown. Interactive prompts (permission
requests, AskUserQuestion, plan approval, MCP elicitation) are always shown too
— hiding them would deadlock the session. Everything else — thinking, tool-use,
todos, the session-start embed, and compaction notices — is individually
toggleable so an instance can be as quiet or as verbose as it likes.

All elements default to *shown* (backward compatible). Set the matching
``HIDE_*`` env var (``1``/``true``/``yes``/``on``) to turn one off, e.g.
``HIDE_TOOL_USE=true`` to suppress tool-use embeds. The per-channel
``chat_only`` flag still works as a master switch that hides everything.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUTHY = {"1", "true", "yes", "on"}


def _is_hidden(environ: Mapping[str, str], key: str) -> bool:
    return environ.get(key, "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class DisplayConfig:
    """Independent on/off switches for each informational display element."""

    show_thinking: bool = True
    show_tool_use: bool = True
    show_todos: bool = True
    show_session_start: bool = True
    show_compaction: bool = True

    @classmethod
    def all_visible(cls) -> DisplayConfig:
        """Everything shown — the default, full-output behaviour."""
        return cls()

    @classmethod
    def all_hidden(cls) -> DisplayConfig:
        """Everything hidden — the chat_only-equivalent behaviour."""
        return cls(
            show_thinking=False,
            show_tool_use=False,
            show_todos=False,
            show_session_start=False,
            show_compaction=False,
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> DisplayConfig:
        """Build from ``HIDE_*`` env vars. Unset/falsey → element stays visible."""
        env = os.environ if environ is None else environ
        return cls(
            show_thinking=not _is_hidden(env, "HIDE_THINKING"),
            show_tool_use=not _is_hidden(env, "HIDE_TOOL_USE"),
            show_todos=not _is_hidden(env, "HIDE_TODOS"),
            show_session_start=not _is_hidden(env, "HIDE_SESSION_START"),
            show_compaction=not _is_hidden(env, "HIDE_COMPACTION"),
        )
