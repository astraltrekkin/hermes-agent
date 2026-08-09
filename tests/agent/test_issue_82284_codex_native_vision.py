"""Regression tests for #82284 — openai-codex native image routing.

The ChatGPT Codex OAuth backend (``/backend-api/codex/responses``) returns
``server_error`` on ``input_image`` parts while text-only requests succeed.
Hermes must not route user-attached images natively through openai-codex by
default, and vision auto-detect must fall through to aggregator backends.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agent.image_routing import _lookup_supports_vision, decide_image_input_mode


def _default_codex_cfg() -> dict:
    return {
        "model": {"provider": "openai-codex", "model": "gpt-5.5"},
        "auxiliary": {"vision": {"provider": "auto", "model": ""}},
    }


class TestIssue82284CodexNativeVisionRouting:
    """Reproduces the routing decision described in #82284."""

    def test_default_openai_codex_supports_vision_lookup(self):
        cfg = _default_codex_cfg()
        assert _lookup_supports_vision("openai-codex", "gpt-5.5", cfg) is False

    def test_default_openai_codex_image_mode_is_text_not_native(self):
        cfg = _default_codex_cfg()
        assert decide_image_input_mode("openai-codex", "gpt-5.5", cfg) == "text"

    def test_explicit_supports_vision_true_opt_in_restores_native(self):
        """Power users can re-enable native vision when the backend supports it."""
        cfg = {
            "model": {
                "provider": "openai-codex",
                "model": "gpt-5.5",
                "supports_vision": True,
            },
            "auxiliary": {"vision": {"provider": "auto", "model": ""}},
        }
        assert _lookup_supports_vision("openai-codex", "gpt-5.5", cfg) is True
        assert decide_image_input_mode("openai-codex", "gpt-5.5", cfg) == "native"


class TestIssue82284VisionAutoDetectSkipsCodex:
    def test_auto_vision_skips_openai_codex_main_provider(self, monkeypatch):
        from agent import auxiliary_client as aux

        monkeypatch.setattr(aux, "_read_main_provider", lambda: "openai-codex")
        monkeypatch.setattr(aux, "_read_main_model", lambda: "gpt-5.5")
        monkeypatch.setattr(
            aux,
            "_try_openrouter",
            lambda **_: (object(), "google/gemini-2.5-flash"),
        )

        provider, client, model = aux.resolve_vision_provider_client(provider="auto")
        assert provider == "openrouter"
        assert client is not None
        assert model == "google/gemini-2.5-flash"


class TestIssue82284VisionToolFastPath:
    def test_openai_codex_does_not_use_native_tool_result_fast_path(self):
        from tools.vision_tools import _supports_media_in_tool_results

        assert _supports_media_in_tool_results("openai-codex", "gpt-5.5") is False
