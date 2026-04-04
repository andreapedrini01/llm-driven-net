"""
Unit tests for change_summary module.

Cases covered:
- LLM summary appears in a separate section after the structured summary (Req 4.3)
- generate_llm_summary returns None when ChatGPTClient raises exception (Req 3.3)
- generate_llm_summary returns content on success
- generate_llm_summary returns None on empty content
"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

import pytest

from src.models.actions import NetworkAction, ActionType
from northbound_script_generator.action_processor import ExecutionResult, ExecutionStatus
from src.services.change_summary import generate_summary, generate_llm_summary
from src.services.chatgpt_client import ChatGPTResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_action(action_id="act-1", action_type=ActionType.FLOW_MOD, target="sw1"):
    return NetworkAction(
        id=action_id,
        type=action_type,
        target=target,
        parameters={"match": {"nw_src": "10.0.0.1"}, "actions": []},
    )


def _make_result(action_id="act-1", status=ExecutionStatus.SUCCESS, error=None):
    return ExecutionResult(
        action_id=action_id,
        status=status,
        timestamp=datetime.now(),
        duration=0.45,
        message="done",
        error=error,
    )


def _make_chatgpt_response(content: str) -> ChatGPTResponse:
    return ChatGPTResponse(
        content=content,
        model="gpt-test",
        tokens_used=10,
        latency=0.1,
        finish_reason="stop",
        timestamp=datetime.now(),
    )


# ---------------------------------------------------------------------------
# Test: LLM summary appears in a separate section (Req 4.3)
# ---------------------------------------------------------------------------

class TestLLMSummarySection:
    """Validates: Requirement 4.3"""

    def test_llm_summary_in_separate_section(self):
        action = _make_action()
        result = _make_result()
        llm_text = "Traffic was blocked between h1 and h2."

        summary = generate_summary(
            intent_text="block traffic",
            confidence=0.5,
            actions=[action],
            results=[result],
            llm_summary=llm_text,
        )

        assert "LLM Summary" in summary, "LLM Summary section header missing"
        assert llm_text in summary, "LLM summary text missing from output"

        # LLM section must appear after the footer (RESULT line)
        result_pos = summary.find("RESULT:")
        llm_pos = summary.find("LLM Summary")
        assert llm_pos > result_pos, "LLM Summary section should appear after the footer"

    def test_no_llm_section_when_none(self):
        action = _make_action()
        result = _make_result()

        summary = generate_summary(
            intent_text="block traffic",
            confidence=0.9,
            actions=[action],
            results=[result],
            llm_summary=None,
        )

        assert "LLM Summary" not in summary, "LLM Summary section should not appear when llm_summary is None"

    def test_no_llm_section_when_empty(self):
        action = _make_action()
        result = _make_result()

        summary = generate_summary(
            intent_text="block traffic",
            confidence=0.9,
            actions=[action],
            results=[result],
            llm_summary="",
        )

        assert "LLM Summary" not in summary, "LLM Summary section should not appear when llm_summary is empty"


# ---------------------------------------------------------------------------
# Test: generate_llm_summary returns None on ChatGPTClient exception (Req 3.3)
# ---------------------------------------------------------------------------

class TestGenerateLLMSummaryErrorHandling:
    """Validates: Requirement 3.3"""

    def test_returns_none_on_exception(self):
        client = MagicMock()
        client.generate_response = AsyncMock(side_effect=RuntimeError("API unavailable"))

        action = _make_action()
        result = _make_result()

        output = asyncio.get_event_loop().run_until_complete(
            generate_llm_summary(client, "block traffic", [action], [result])
        )

        assert output is None, "generate_llm_summary should return None on exception"

    def test_returns_content_on_success(self):
        client = MagicMock()
        client.generate_response = AsyncMock(
            return_value=_make_chatgpt_response("Traffic was blocked successfully.")
        )

        action = _make_action()
        result = _make_result()

        output = asyncio.get_event_loop().run_until_complete(
            generate_llm_summary(client, "block traffic", [action], [result])
        )

        assert output == "Traffic was blocked successfully."

    def test_returns_none_on_empty_content(self):
        client = MagicMock()
        client.generate_response = AsyncMock(
            return_value=_make_chatgpt_response("   ")
        )

        action = _make_action()
        result = _make_result()

        output = asyncio.get_event_loop().run_until_complete(
            generate_llm_summary(client, "block traffic", [action], [result])
        )

        assert output is None, "generate_llm_summary should return None for whitespace-only content"
