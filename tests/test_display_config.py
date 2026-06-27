"""Tests for DisplayConfig — per-element output toggles."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from claude_discord.display_config import DisplayConfig

ELEMENTS = [
    "show_thinking",
    "show_tool_use",
    "show_todos",
    "show_session_start",
    "show_compaction",
]


class TestDefaults:
    def test_default_everything_visible(self) -> None:
        cfg = DisplayConfig()
        assert all(getattr(cfg, e) for e in ELEMENTS)

    def test_all_visible(self) -> None:
        assert all(getattr(DisplayConfig.all_visible(), e) for e in ELEMENTS)

    def test_all_hidden(self) -> None:
        assert not any(getattr(DisplayConfig.all_hidden(), e) for e in ELEMENTS)

    def test_frozen(self) -> None:
        cfg = DisplayConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.show_tool_use = False  # type: ignore[misc]


class TestFromEnv:
    def test_empty_env_all_visible(self) -> None:
        assert DisplayConfig.from_env({}) == DisplayConfig.all_visible()

    def test_hide_tool_use(self) -> None:
        cfg = DisplayConfig.from_env({"HIDE_TOOL_USE": "true"})
        assert cfg.show_tool_use is False
        # Other elements stay visible.
        assert cfg.show_thinking is True
        assert cfg.show_todos is True
        assert cfg.show_session_start is True
        assert cfg.show_compaction is True

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", "on", " on "])
    def test_truthy_values_hide(self, value: str) -> None:
        assert DisplayConfig.from_env({"HIDE_THINKING": value}).show_thinking is False

    @pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "nope"])
    def test_falsey_values_stay_visible(self, value: str) -> None:
        assert DisplayConfig.from_env({"HIDE_THINKING": value}).show_thinking is True

    def test_each_hide_var_maps_to_its_element(self) -> None:
        mapping = {
            "HIDE_THINKING": "show_thinking",
            "HIDE_TOOL_USE": "show_tool_use",
            "HIDE_TODOS": "show_todos",
            "HIDE_SESSION_START": "show_session_start",
            "HIDE_COMPACTION": "show_compaction",
        }
        for env_key, attr in mapping.items():
            cfg = DisplayConfig.from_env({env_key: "true"})
            assert getattr(cfg, attr) is False, f"{env_key} should hide {attr}"
            # Every other element remains visible.
            for other in ELEMENTS:
                if other != attr:
                    assert getattr(cfg, other) is True

    def test_multiple_hidden(self) -> None:
        cfg = DisplayConfig.from_env({"HIDE_TOOL_USE": "1", "HIDE_TODOS": "1"})
        assert cfg.show_tool_use is False
        assert cfg.show_todos is False
        assert cfg.show_thinking is True
