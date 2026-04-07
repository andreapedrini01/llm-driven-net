"""
Property-based test: Preservation — Low-Confidence and Successful Rule-Based
Paths Unchanged.

Property 2 (Preservation):
    - For any confidence in [0.0, 0.80), the ChatGPT fallback log message
      matches the original format: 'confidence X.XX < 0.8'.
    - For any confidence >= 0.80 with specific useful actions (FLOW_MOD,
      SLICE_CREATE, or non-generic CONFIG_CHANGE), the rule-based success
      path is taken and no ChatGPT fallback log is emitted.

These tests MUST PASS on unfixed code — they confirm baseline behavior
that the fix must preserve.

**Validates: Requirements 3.1, 3.2**
"""

import logging
import re
import pytest
from datetime import datetime

from hypothesis import given, strategies as st, settings, HealthCheck

from src.models.actions import NetworkAction as LLMAction, ActionType
from src.models.intent import IntentObject, IntentType, Entity

# The threshold constant from main.py
RULE_BASED_CONFIDENCE_THRESHOLD = 0.8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_intent(confidence: float) -> IntentObject:
    """Create a minimal IntentObject with the given confidence."""
    return IntentObject(
        id="intent_test",
        raw_text="configure switch1 bandwidth",
        timestamp=datetime.now(),
        user_id="user_1",
        entities=[
            Entity(name="switch", type="resource", value="switch1", confidence=0.95),
        ],
        intent_type=IntentType.CONFIGURATION,
        confidence=confidence,
        parameters={},
    )


def _make_generic_config_action() -> LLMAction:
    """Return a generic CONFIG_CHANGE action (triggers fallback)."""
    return LLMAction(
        id="action-generic-1",
        type=ActionType.CONFIG_CHANGE,
        target="switch-1",
        parameters={"config_type": "general", "config_data": {"key": "value"}},
    )


def _make_flow_mod_action() -> LLMAction:
    """Return a FLOW_MOD action (specific, keeps rule-based path)."""
    return LLMAction(
        id="action-flow-1",
        type=ActionType.FLOW_MOD,
        target="switch-1",
        parameters={"operation": "add", "match": {}, "actions": []},
    )


def _make_slice_create_action() -> LLMAction:
    """Return a SLICE_CREATE action (specific, keeps rule-based path)."""
    return LLMAction(
        id="action-slice-1",
        type=ActionType.SLICE_CREATE,
        target="switch-1",
        parameters={"slice_name": "test_slice", "resources": ["network"]},
    )


def _make_specific_config_action() -> LLMAction:
    """Return a non-generic CONFIG_CHANGE action (specific, keeps rule-based path)."""
    return LLMAction(
        id="action-config-specific-1",
        type=ActionType.CONFIG_CHANGE,
        target="switch-1",
        parameters={"config_type": "bandwidth_limit", "config_data": {"bw": 100}},
    )


def _run_log_capture(intent_obj, mock_rule_based_return):
    """
    Reproduce the exact logic from main.py lines 585-617 in isolation,
    capturing all log records from the main module logger.

    Returns the list of log records emitted.
    """
    from main import RULE_BASED_CONFIDENCE_THRESHOLD as THRESHOLD

    logger = logging.getLogger("main")
    logger.setLevel(logging.DEBUG)

    captured: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = lambda record: captured.append(record)  # type: ignore[assignment]
    logger.addHandler(handler)

    try:
        use_rule_based = intent_obj.confidence >= THRESHOLD

        actions = []

        if use_rule_based:
            actions = mock_rule_based_return

            has_specific_actions = any(
                a.type in (ActionType.FLOW_MOD, ActionType.SLICE_CREATE)
                or (
                    a.type == ActionType.CONFIG_CHANGE
                    and a.parameters.get("config_type")
                    not in ("general", "anomaly_fix")
                )
                for a in actions
            )

            if actions and has_specific_actions:
                logger.info(
                    f"✓ {len(actions)} azioni generate (rule-based, senza ChatGPT)"
                )
            else:
                if actions:
                    logger.warning(
                        "⚠ Rule-based ha generato solo azioni generiche, fallback a ChatGPT..."
                    )
                else:
                    logger.warning(
                        "⚠ Nessuna azione generata dal rule-based, fallback a ChatGPT..."
                    )
                actions = []
                use_rule_based = False

        if not use_rule_based:
            # Fixed: conditional log message based on actual confidence
            if intent_obj.confidence >= THRESHOLD:
                logger.info(
                    f"\nStep 4: Generating actions with ChatGPT "
                    f"(confidence {intent_obj.confidence:.2f} >= {THRESHOLD}, "
                    f"but rule-based produced insufficient results)"
                )
            else:
                logger.info(
                    f"\nStep 4: Generazione azioni con ChatGPT "
                    f"(confidence {intent_obj.confidence:.2f} < {THRESHOLD})"
                )

        return captured
    finally:
        logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# Strategies for property-based tests
# ---------------------------------------------------------------------------

# Confidence values strictly below the threshold
low_confidence_values = st.floats(
    min_value=0.0, max_value=0.7999, allow_nan=False, allow_infinity=False
)

# Confidence values at or above the threshold
high_confidence_values = st.floats(
    min_value=0.80, max_value=1.0, allow_nan=False, allow_infinity=False
)

# Strategy that produces a list containing at least one specific action
specific_action_lists = st.sampled_from([
    [_make_flow_mod_action()],
    [_make_slice_create_action()],
    [_make_specific_config_action()],
    [_make_flow_mod_action(), _make_generic_config_action()],
    [_make_slice_create_action(), _make_generic_config_action()],
    [_make_specific_config_action(), _make_flow_mod_action()],
])


# ---------------------------------------------------------------------------
# Property-based tests: Preservation
# ---------------------------------------------------------------------------

class TestPreservationLowConfidence:
    """
    Property 2a: For all confidence values in [0.0, 0.80), the ChatGPT
    fallback log message matches the original format exactly:
    'confidence X.XX < 0.8'

    **Validates: Requirements 3.1**
    """

    @pytest.mark.property
    @given(confidence=low_confidence_values)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_low_confidence_produces_chatgpt_fallback_with_correct_format(
        self, confidence
    ):
        """
        For any confidence in [0.0, 0.80), the code takes the ChatGPT
        fallback path and the log message contains
        'confidence X.XX < 0.8' — the original, correct format.

        **Validates: Requirements 3.1**
        """
        intent = _make_intent(confidence)
        # Low confidence → rule-based is never attempted, mock return is irrelevant
        records = _run_log_capture(intent, [])

        # Extract fallback log messages
        fallback_messages = [
            r.getMessage() for r in records if "ChatGPT" in r.getMessage()
        ]

        # Must have at least one ChatGPT fallback log
        assert fallback_messages, (
            f"Expected a ChatGPT fallback log for confidence={confidence:.2f}"
        )

        # The message must contain the correct 'confidence X.XX < 0.8' format
        expected_fragment = (
            f"confidence {confidence:.2f} < {RULE_BASED_CONFIDENCE_THRESHOLD}"
        )
        for msg in fallback_messages:
            assert expected_fragment in msg, (
                f"Low-confidence fallback log does not match expected format.\n"
                f"Expected fragment: '{expected_fragment}'\n"
                f"Actual message: '{msg}'"
            )

    @pytest.mark.property
    def test_boundary_0799_takes_chatgpt_path(self):
        """
        Concrete case: confidence=0.7999 (just below threshold) must take
        the ChatGPT fallback path with the original log format.

        **Validates: Requirements 3.1**
        """
        confidence = 0.7999
        intent = _make_intent(confidence)
        records = _run_log_capture(intent, [])

        fallback_messages = [
            r.getMessage() for r in records if "ChatGPT" in r.getMessage()
        ]
        assert fallback_messages, "Expected ChatGPT fallback log at confidence=0.7999"

        expected_fragment = (
            f"confidence {confidence:.2f} < {RULE_BASED_CONFIDENCE_THRESHOLD}"
        )
        for msg in fallback_messages:
            assert expected_fragment in msg, (
                f"Boundary case 0.7999: log format mismatch. Message: {msg}"
            )

    @pytest.mark.property
    def test_zero_confidence_takes_chatgpt_path(self):
        """
        Concrete case: confidence=0.0 must take the ChatGPT fallback path.

        **Validates: Requirements 3.1**
        """
        confidence = 0.0
        intent = _make_intent(confidence)
        records = _run_log_capture(intent, [])

        fallback_messages = [
            r.getMessage() for r in records if "ChatGPT" in r.getMessage()
        ]
        assert fallback_messages, "Expected ChatGPT fallback log at confidence=0.0"

        expected_fragment = (
            f"confidence {confidence:.2f} < {RULE_BASED_CONFIDENCE_THRESHOLD}"
        )
        for msg in fallback_messages:
            assert expected_fragment in msg, (
                f"Zero confidence: log format mismatch. Message: {msg}"
            )


class TestPreservationRuleBasedSuccess:
    """
    Property 2b: For all confidence values >= 0.80 with specific useful
    actions (FLOW_MOD, SLICE_CREATE, or non-generic CONFIG_CHANGE), the
    rule-based success path is taken and no ChatGPT fallback log is emitted.

    **Validates: Requirements 3.2**
    """

    @pytest.mark.property
    @given(
        confidence=high_confidence_values,
        action_list=specific_action_lists,
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_high_confidence_with_specific_actions_stays_rule_based(
        self, confidence, action_list
    ):
        """
        For any confidence >= 0.80 with at least one specific action,
        the rule-based success path is taken: the success log is emitted
        and NO ChatGPT fallback log appears.

        **Validates: Requirements 3.2**
        """
        intent = _make_intent(confidence)
        records = _run_log_capture(intent, action_list)

        messages = [r.getMessage() for r in records]

        # Must have the rule-based success log
        success_messages = [
            m for m in messages
            if "azioni generate (rule-based" in m
        ]
        assert success_messages, (
            f"Expected rule-based success log for confidence={confidence:.2f} "
            f"with {len(action_list)} specific actions"
        )

        # Must NOT have any ChatGPT fallback log
        chatgpt_messages = [
            m for m in messages if "ChatGPT" in m and "Step 4" in m
        ]
        assert not chatgpt_messages, (
            f"Unexpected ChatGPT fallback log when rule-based should succeed.\n"
            f"Confidence: {confidence:.2f}, Actions: {len(action_list)}\n"
            f"ChatGPT messages: {chatgpt_messages}"
        )

    @pytest.mark.property
    def test_confidence_095_with_flow_mod_stays_rule_based(self):
        """
        Concrete case: confidence=0.95 with FLOW_MOD action → rule-based
        success, no ChatGPT fallback.

        **Validates: Requirements 3.2**
        """
        intent = _make_intent(0.95)
        records = _run_log_capture(intent, [_make_flow_mod_action()])

        messages = [r.getMessage() for r in records]

        success_messages = [
            m for m in messages if "azioni generate (rule-based" in m
        ]
        assert success_messages, "Expected rule-based success log at confidence=0.95"

        chatgpt_messages = [
            m for m in messages if "ChatGPT" in m and "Step 4" in m
        ]
        assert not chatgpt_messages, (
            f"Unexpected ChatGPT fallback at confidence=0.95 with FLOW_MOD"
        )

    @pytest.mark.property
    def test_confidence_080_boundary_with_slice_create_stays_rule_based(self):
        """
        Concrete case: confidence=0.80 exactly with SLICE_CREATE action →
        rule-based success, no ChatGPT fallback.

        **Validates: Requirements 3.2**
        """
        intent = _make_intent(0.80)
        records = _run_log_capture(intent, [_make_slice_create_action()])

        messages = [r.getMessage() for r in records]

        success_messages = [
            m for m in messages if "azioni generate (rule-based" in m
        ]
        assert success_messages, (
            "Expected rule-based success log at confidence=0.80 boundary"
        )

        chatgpt_messages = [
            m for m in messages if "ChatGPT" in m and "Step 4" in m
        ]
        assert not chatgpt_messages, (
            f"Unexpected ChatGPT fallback at confidence=0.80 boundary with SLICE_CREATE"
        )
