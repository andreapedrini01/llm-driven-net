"""
Property-based tests for change_summary module.

Properties implemented:
- Property 1: Completeness of summary per action (Requirements 1.1, 1.2, 1.3)
- Property 2: Mode and confidence in summary (Requirement 1.4)
- Property 3: Correctness of state diff (Requirements 2.1, 2.2)
- Property 4: LLM prompt completeness (Requirement 3.4)
- Property 5: Formatting and correct counts (Requirements 4.1, 4.2)
- Property 6: Resilience to malformed inputs (Requirement 5.3)
"""

from datetime import datetime
from typing import Dict, Any, Optional

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume

from src.models.actions import NetworkAction, ActionType
from northbound_script_generator.action_processor import ExecutionResult, ExecutionStatus
from src.services.change_summary import (
    format_action_detail,
    compute_state_diff,
    format_summary_header,
    format_summary_footer,
    generate_summary,
    build_llm_prompt,
)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

action_types = st.sampled_from(list(ActionType))

execution_statuses = st.sampled_from(list(ExecutionStatus))

safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs"), whitelist_characters="-_"),
    min_size=1,
    max_size=30,
)

action_ids = st.from_regex(r"[a-zA-Z0-9_-]{1,20}", fullmatch=True)

targets = st.from_regex(r"[a-zA-Z0-9._:-]{1,20}", fullmatch=True)

param_values = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.text(alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=10),
    st.booleans(),
)

param_dicts = st.dictionaries(
    keys=st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=8),
    values=param_values,
    max_size=5,
)

priorities = st.integers(min_value=0, max_value=65535)
timeouts = st.integers(min_value=1, max_value=3600)


@st.composite
def network_actions(draw):
    """Generate a valid NetworkAction."""
    return NetworkAction(
        id=draw(action_ids),
        type=draw(action_types),
        target=draw(targets),
        parameters=draw(param_dicts),
        priority=draw(priorities),
        timeout=draw(timeouts),
    )


@st.composite
def execution_results(draw, action_id=None, status=None):
    """Generate a valid ExecutionResult."""
    aid = action_id or draw(action_ids)
    st_status = status or draw(execution_statuses)
    error = None
    if st_status != ExecutionStatus.SUCCESS:
        error = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
            min_size=1, max_size=40,
        ))
    return ExecutionResult(
        action_id=aid,
        status=st_status,
        timestamp=datetime.now(),
        duration=draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
        message=draw(safe_text),
        error=error,
    )


@st.composite
def action_result_pairs(draw):
    """Generate a matching (NetworkAction, ExecutionResult) pair."""
    action = draw(network_actions())
    result = draw(execution_results(action_id=action.id))
    return action, result


@st.composite
def success_pairs(draw):
    """Generate a pair where the result is SUCCESS."""
    action = draw(network_actions())
    result = draw(execution_results(action_id=action.id, status=ExecutionStatus.SUCCESS))
    return action, result


@st.composite
def failed_pairs(draw):
    """Generate a pair where the result is FAILED."""
    action = draw(network_actions())
    result = draw(execution_results(action_id=action.id, status=ExecutionStatus.FAILED))
    return action, result


flat_dict_values = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.text(alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=10),
    st.booleans(),
)

state_dicts = st.dictionaries(
    keys=st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=8),
    values=flat_dict_values,
    min_size=0,
    max_size=8,
)



# ---------------------------------------------------------------------------
# Property 1: Completeness of summary per action
# Feature: network-change-summary, Property 1: Completeness of summary per action
# Validates: Requirements 1.1, 1.2, 1.3
# ---------------------------------------------------------------------------

class TestCompletenessPerAction:
    """
    Property 1: Completeness of summary per action

    For any (NetworkAction, ExecutionResult) pair, the summary must contain
    action type, target, duration. If SUCCESS, must contain parameter values.
    If FAILED, must contain error message.

    **Validates: Requirements 1.1, 1.2, 1.3**
    """

    @given(pair=action_result_pairs())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_summary_contains_type_target_duration(self, pair):
        # Feature: network-change-summary, Property 1: Completeness of summary per action
        action, result = pair
        output = format_action_detail(action, result)

        assert action.type.value in output, f"Action type '{action.type.value}' not found in output"
        assert action.target in output, f"Target '{action.target}' not found in output"
        assert f"{result.duration:.2f}s" in output, f"Duration '{result.duration:.2f}s' not found in output"

    @given(pair=success_pairs())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_success_contains_parameter_values(self, pair):
        # Feature: network-change-summary, Property 1: Completeness of summary per action
        action, result = pair
        assume(len(action.parameters) > 0)
        output = format_action_detail(action, result)

        for value in action.parameters.values():
            assert str(value) in output, f"Parameter value '{value}' not found in output"

    @given(pair=failed_pairs())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_failure_contains_error_message(self, pair):
        # Feature: network-change-summary, Property 1: Completeness of summary per action
        action, result = pair
        assume(result.error is not None and len(result.error.strip()) > 0)
        output = format_action_detail(action, result)

        assert result.error in output, f"Error message '{result.error}' not found in output"


# ---------------------------------------------------------------------------
# Property 2: Mode and confidence in summary
# Feature: network-change-summary, Property 2: Mode and confidence in summary
# Validates: Requirement 1.4
# ---------------------------------------------------------------------------

class TestModeAndConfidence:
    """
    Property 2: Mode and confidence in summary

    For any confidence 0.0-1.0, summary must show "Rule-based" if >= 0.8,
    "LLM" if < 0.8, and must contain the numeric confidence value.

    **Validates: Requirement 1.4**
    """

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        intent=safe_text,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_header_shows_correct_mode(self, confidence, intent):
        # Feature: network-change-summary, Property 2: Mode and confidence in summary
        header = format_summary_header(intent, confidence)

        if confidence >= 0.8:
            assert "Rule-based" in header, "Expected 'Rule-based' for confidence >= 0.8"
        else:
            assert "LLM" in header, "Expected 'LLM' for confidence < 0.8"

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        intent=safe_text,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_header_contains_confidence_value(self, confidence, intent):
        # Feature: network-change-summary, Property 2: Mode and confidence in summary
        header = format_summary_header(intent, confidence)

        assert f"{confidence:.2f}" in header, f"Confidence value '{confidence:.2f}' not found in header"


# ---------------------------------------------------------------------------
# Property 3: Correctness of state diff
# Feature: network-change-summary, Property 3: Correctness of state diff
# Validates: Requirements 2.1, 2.2
# ---------------------------------------------------------------------------

class TestStateDiffCorrectness:
    """
    Property 3: Correctness of state diff

    For any two dicts, diff must correctly report all added, removed,
    modified keys. If either is None, diff must be None and no errors.

    **Validates: Requirements 2.1, 2.2**
    """

    @given(before=state_dicts, after=state_dicts)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_diff_reports_added_removed_modified(self, before, after):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        diff = compute_state_diff(before, after)

        added = set(after.keys()) - set(before.keys())
        removed = set(before.keys()) - set(after.keys())
        modified = {k for k in set(before.keys()) & set(after.keys()) if before[k] != after[k]}

        if not added and not removed and not modified:
            assert diff is None, "Expected None diff when states are identical"
        else:
            assert diff is not None, "Expected non-None diff when states differ"
            for key in added:
                assert f"+ {key}" in diff, f"Added key '{key}' not reported in diff"
            for key in removed:
                assert f"- {key}" in diff, f"Removed key '{key}' not reported in diff"
            for key in modified:
                assert f"~ {key}" in diff, f"Modified key '{key}' not reported in diff"

    @given(d=state_dicts)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_none_before_returns_none(self, d):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        result = compute_state_diff(None, d)
        assert result is None, "Expected None when state_before is None"

    @given(d=state_dicts)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_none_after_returns_none(self, d):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        result = compute_state_diff(d, None)
        assert result is None, "Expected None when state_after is None"

    def test_both_none_returns_none(self):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        assert compute_state_diff(None, None) is None, "Expected None when both states are None"

    @given(d=state_dicts)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_identical_states_returns_none(self, d):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        result = compute_state_diff(d, d)
        assert result is None, "Expected None when before and after are identical"

    @given(data=st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_modified_keys_show_both_values(self, data):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        # Build dicts that share at least one key with different values
        shared_key = data.draw(st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=8))
        val_before = data.draw(st.integers(min_value=0, max_value=499))
        val_after = data.draw(st.integers(min_value=500, max_value=999))
        before = data.draw(state_dicts)
        after = data.draw(state_dicts)
        before[shared_key] = val_before
        after[shared_key] = val_after

        diff = compute_state_diff(before, after)
        assert diff is not None
        assert str(val_before) in diff, f"Old value '{val_before}' not shown in diff"
        assert str(val_after) in diff, f"New value '{val_after}' not shown in diff"

    @given(data=st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_removed_keys_marked_as_removed(self, data):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        # Ensure before has at least one key not in after
        removed_key = data.draw(st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=8))
        before = data.draw(state_dicts)
        after = data.draw(state_dicts)
        before[removed_key] = data.draw(flat_dict_values)
        after.pop(removed_key, None)

        diff = compute_state_diff(before, after)
        assert diff is not None
        assert f"- {removed_key}: (removed)" in diff, f"Removed key '{removed_key}' not marked with '(removed)'"

    @given(data=st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_nested_dicts_flatten_to_dotted_keys(self, data):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        # Build nested before/after with a known nested key that differs
        inner_key = data.draw(st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=5))
        outer_key = data.draw(st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=5))
        val_before = data.draw(st.integers(min_value=0, max_value=500))
        val_after = data.draw(st.integers(min_value=501, max_value=1000))

        before = {outer_key: {inner_key: val_before}}
        after = {outer_key: {inner_key: val_after}}

        diff = compute_state_diff(before, after)
        assert diff is not None, "Expected diff for nested dicts with different values"
        expected_key = f"{outer_key}.{inner_key}"
        assert f"~ {expected_key}" in diff, f"Nested modified key '{expected_key}' not in diff"
        assert str(val_before) in diff
        assert str(val_after) in diff

    @given(data=st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_diff_count_matches_actual_changes(self, data):
        # Feature: network-change-summary, Property 3: Correctness of state diff
        before = data.draw(state_dicts)
        after = data.draw(state_dicts)

        added = set(after.keys()) - set(before.keys())
        removed = set(before.keys()) - set(after.keys())
        modified = {k for k in set(before.keys()) & set(after.keys()) if before[k] != after[k]}
        total_changes = len(added) + len(removed) + len(modified)
        assume(total_changes > 0)

        diff = compute_state_diff(before, after)
        assert diff is not None

        plus_count = diff.count("\n  + ")
        tilde_count = diff.count("\n  ~ ")
        minus_count = diff.count("\n  - ")
        assert plus_count == len(added), f"Added count mismatch: {plus_count} vs {len(added)}"
        assert minus_count == len(removed), f"Removed count mismatch: {minus_count} vs {len(removed)}"
        assert tilde_count == len(modified), f"Modified count mismatch: {tilde_count} vs {len(modified)}"


# ---------------------------------------------------------------------------
# Property 4: LLM prompt completeness
# Feature: network-change-summary, Property 4: LLM prompt completeness
# Validates: Requirement 3.4
# ---------------------------------------------------------------------------

class TestLLMPromptCompleteness:
    """
    Property 4: LLM prompt completeness

    For any intent + actions + results, prompt must contain intent text,
    type/target of each action, status of each result.

    **Validates: Requirement 3.4**
    """

    @given(
        intent=safe_text,
        actions=st.lists(network_actions(), min_size=1, max_size=5),
        results=st.lists(execution_results(), min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_contains_intent(self, intent, actions, results):
        # Feature: network-change-summary, Property 4: LLM prompt completeness
        prompt = build_llm_prompt(intent, actions, results)
        assert intent in prompt, f"Intent text '{intent}' not found in prompt"

    @given(
        intent=safe_text,
        actions=st.lists(network_actions(), min_size=1, max_size=5),
        results=st.lists(execution_results(), min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_contains_action_type_and_target(self, intent, actions, results):
        # Feature: network-change-summary, Property 4: LLM prompt completeness
        prompt = build_llm_prompt(intent, actions, results)
        for action in actions:
            assert action.type.value in prompt, f"Action type '{action.type.value}' not in prompt"
            assert action.target in prompt, f"Action target '{action.target}' not in prompt"

    @given(
        intent=safe_text,
        actions=st.lists(network_actions(), min_size=1, max_size=5),
        results=st.lists(execution_results(), min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_contains_result_statuses(self, intent, actions, results):
        # Feature: network-change-summary, Property 4: LLM prompt completeness
        prompt = build_llm_prompt(intent, actions, results)
        for result in results:
            assert result.status.value in prompt, f"Result status '{result.status.value}' not in prompt"

    @given(
        intent=safe_text,
        actions=st.lists(network_actions(), min_size=1, max_size=5),
        results=st.lists(execution_results(), min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_contains_error_for_failed_results(self, intent, actions, results):
        # Feature: network-change-summary, Property 4: LLM prompt completeness
        prompt = build_llm_prompt(intent, actions, results)
        for result in results:
            if result.error:
                assert result.error in prompt, (
                    f"Error message '{result.error}' not found in prompt for failed result"
                )

    @given(
        intent=safe_text,
        actions=st.lists(network_actions(), min_size=1, max_size=5),
        results=st.lists(execution_results(), min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_action_count_matches_input(self, intent, actions, results):
        # Feature: network-change-summary, Property 4: LLM prompt completeness
        prompt = build_llm_prompt(intent, actions, results)
        action_lines = [line for line in prompt.splitlines() if line.strip().startswith("- Action ")]
        assert len(action_lines) == len(actions), (
            f"Expected {len(actions)} action entries, found {len(action_lines)}"
        )

    @given(
        intent=safe_text,
        actions=st.lists(network_actions(), min_size=1, max_size=5),
        results=st.lists(execution_results(), min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_result_count_matches_input(self, intent, actions, results):
        # Feature: network-change-summary, Property 4: LLM prompt completeness
        prompt = build_llm_prompt(intent, actions, results)
        result_lines = [line for line in prompt.splitlines() if line.strip().startswith("- Result ")]
        assert len(result_lines) == len(results), (
            f"Expected {len(results)} result entries, found {len(result_lines)}"
        )

    @given(intent=safe_text)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_with_empty_lists(self, intent):
        # Feature: network-change-summary, Property 4: LLM prompt completeness
        prompt = build_llm_prompt(intent, [], [])
        assert intent in prompt, "Intent must be present even with empty lists"
        action_lines = [line for line in prompt.splitlines() if line.strip().startswith("- Action ")]
        result_lines = [line for line in prompt.splitlines() if line.strip().startswith("- Result ")]
        assert len(action_lines) == 0, "No action entries expected for empty actions list"
        assert len(result_lines) == 0, "No result entries expected for empty results list"



# ---------------------------------------------------------------------------
# Property 5: Formatting and correct counts
# Feature: network-change-summary, Property 5: Formatting and correct counts
# Validates: Requirements 4.1, 4.2
# ---------------------------------------------------------------------------

class TestFormattingAndCounts:
    """
    Property 5: Formatting and correct counts

    For any list of ExecutionResult, footer must contain correct
    success/failure counts matching actual SUCCESS/FAILED counts.
    The summary must use visual separators, status icons (✓/✗),
    and properly ordered sections.

    **Validates: Requirements 4.1, 4.2**
    """

    @given(results=st.lists(execution_results(), min_size=1, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_footer_counts_match_actual(self, results):
        # Feature: network-change-summary, Property 5: Formatting and correct counts
        footer = format_summary_footer(results)

        total = len(results)
        success_count = sum(1 for r in results if r.status == ExecutionStatus.SUCCESS)
        failed_count = total - success_count

        assert f"Succeeded: {success_count}" in footer, (
            f"Expected 'Succeeded: {success_count}' in footer"
        )
        assert f"Failed: {failed_count}" in footer, (
            f"Expected 'Failed: {failed_count}' in footer"
        )
        assert f"{success_count}/{total}" in footer, (
            f"Expected '{success_count}/{total}' in footer"
        )

    @given(pair=action_result_pairs())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_action_detail_has_correct_icon(self, pair):
        # Feature: network-change-summary, Property 5: Formatting and correct counts
        action, result = pair
        output = format_action_detail(action, result)

        if result.status == ExecutionStatus.SUCCESS:
            assert "✓" in output, "Expected ✓ icon for SUCCESS"
        else:
            assert "✗" in output, "Expected ✗ icon for non-SUCCESS"

    @given(results=st.lists(execution_results(), min_size=1, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_footer_percentage_is_correct(self, results):
        # Feature: network-change-summary, Property 5: Formatting and correct counts
        footer = format_summary_footer(results)

        total = len(results)
        success_count = sum(1 for r in results if r.status == ExecutionStatus.SUCCESS)
        expected_pct = success_count / total * 100

        assert f"{expected_pct:.1f}%" in footer, (
            f"Expected '{expected_pct:.1f}%' in footer"
        )

    @given(results=st.lists(execution_results(), min_size=1, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_footer_contains_separators(self, results):
        # Feature: network-change-summary, Property 5: Formatting and correct counts
        footer = format_summary_footer(results)

        assert "═" in footer, "Footer must contain heavy separator characters"

    @given(pairs=st.lists(action_result_pairs(), min_size=1, max_size=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_full_summary_has_icon_per_action(self, pairs):
        # Feature: network-change-summary, Property 5: Formatting and correct counts
        actions = [a for a, _ in pairs]
        results = [r for _, r in pairs]

        summary = generate_summary(
            intent_text="test intent",
            confidence=0.9,
            actions=actions,
            results=results,
        )

        success_count = sum(1 for r in results if r.status == ExecutionStatus.SUCCESS)
        fail_count = len(results) - success_count

        assert summary.count("✓") >= success_count, (
            f"Expected at least {success_count} ✓ icons in summary"
        )
        assert summary.count("✗") >= fail_count, (
            f"Expected at least {fail_count} ✗ icons in summary"
        )

    @given(
        pairs=st.lists(action_result_pairs(), min_size=1, max_size=5),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        intent=safe_text,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_summary_sections_ordered_header_before_footer(self, pairs, confidence, intent):
        # Feature: network-change-summary, Property 5: Formatting and correct counts
        actions = [a for a, _ in pairs]
        results = [r for _, r in pairs]

        summary = generate_summary(
            intent_text=intent,
            confidence=confidence,
            actions=actions,
            results=results,
        )

        header_keyword = "NETWORK CHANGE SUMMARY"
        footer_keyword = "RESULT:"

        header_pos = summary.find(header_keyword)
        footer_pos = summary.find(footer_keyword)

        assert header_pos != -1, "Summary must contain header section"
        assert footer_pos != -1, "Summary must contain footer section"
        assert header_pos < footer_pos, "Header must appear before footer"

    @given(
        pairs=st.lists(action_result_pairs(), min_size=1, max_size=5),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        intent=safe_text,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_summary_footer_counts_consistent_with_icons(self, pairs, confidence, intent):
        # Feature: network-change-summary, Property 5: Formatting and correct counts
        actions = [a for a, _ in pairs]
        results = [r for _, r in pairs]

        summary = generate_summary(
            intent_text=intent,
            confidence=confidence,
            actions=actions,
            results=results,
        )

        success_count = sum(1 for r in results if r.status == ExecutionStatus.SUCCESS)
        failed_count = len(results) - success_count

        assert f"Succeeded: {success_count}" in summary
        assert f"Failed: {failed_count}" in summary


# ---------------------------------------------------------------------------
# Property 6: Resilience to malformed inputs
# Feature: network-change-summary, Property 6: Resilience to malformed inputs
# Validates: Requirement 5.3
# ---------------------------------------------------------------------------

class TestResilienceToMalformedInputs:
    """
    Property 6: Resilience to malformed inputs

    For any input (None, empty lists, missing params), generate_summary
    must not raise exceptions and must return a valid string.

    **Validates: Requirement 5.3**
    """

    # ------------------------------------------------------------------
    # generate_summary: broad fuzz with arbitrary combinations
    # ------------------------------------------------------------------

    @given(
        intent=st.one_of(st.none(), st.just(""), safe_text),
        confidence=st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        actions=st.one_of(st.none(), st.just([]), st.lists(network_actions(), max_size=3)),
        results=st.one_of(st.none(), st.just([]), st.lists(execution_results(), max_size=3)),
        llm_summary=st.one_of(st.none(), st.just(""), safe_text),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_generate_summary_never_raises(self, intent, confidence, actions, results, llm_summary):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        result = generate_summary(
            intent_text=intent,
            confidence=confidence,
            actions=actions,
            results=results,
            llm_summary=llm_summary,
        )
        assert isinstance(result, str), "generate_summary must return a string"
        assert len(result) > 0, "generate_summary must return a non-empty string"

    def test_all_none_inputs(self):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        result = generate_summary(
            intent_text=None,
            confidence=None,
            actions=None,
            results=None,
            llm_summary=None,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_lists(self):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        result = generate_summary(
            intent_text="",
            confidence=0.5,
            actions=[],
            results=[],
        )
        assert isinstance(result, str)
        assert len(result) > 0

    # ------------------------------------------------------------------
    # generate_summary: mismatched action/result list lengths
    # ------------------------------------------------------------------

    @given(
        actions=st.lists(network_actions(), min_size=1, max_size=5),
        results=st.lists(execution_results(), min_size=1, max_size=5),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_mismatched_action_result_lengths(self, actions, results, confidence):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        # Actions and results may have different lengths; must not crash.
        assume(len(actions) != len(results))
        result = generate_summary(
            intent_text="test intent",
            confidence=confidence,
            actions=actions,
            results=results,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    # ------------------------------------------------------------------
    # generate_summary: actions present but results is None/empty
    # ------------------------------------------------------------------

    @given(actions=st.lists(network_actions(), min_size=1, max_size=3))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_actions_without_results(self, actions):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        for results_val in [None, []]:
            result = generate_summary(
                intent_text="test",
                confidence=0.9,
                actions=actions,
                results=results_val,
            )
            assert isinstance(result, str)
            assert len(result) > 0

    # ------------------------------------------------------------------
    # generate_summary: results present but actions is None/empty
    # ------------------------------------------------------------------

    @given(results=st.lists(execution_results(), min_size=1, max_size=3))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_results_without_actions(self, results):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        for actions_val in [None, []]:
            result = generate_summary(
                intent_text="test",
                confidence=0.5,
                actions=actions_val,
                results=results,
            )
            assert isinstance(result, str)
            assert len(result) > 0

    # ------------------------------------------------------------------
    # format_summary_header: resilience to None / extreme confidence
    # ------------------------------------------------------------------

    @given(
        intent=st.one_of(st.none(), st.just(""), safe_text),
        confidence=st.one_of(
            st.none(),
            st.just(0.0),
            st.just(1.0),
            st.floats(allow_nan=False, allow_infinity=False),
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_format_summary_header_never_raises(self, intent, confidence):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        result = format_summary_header(intent, confidence)
        assert isinstance(result, str)
        assert len(result) > 0

    # ------------------------------------------------------------------
    # format_summary_footer: resilience to None / empty results
    # ------------------------------------------------------------------

    @given(
        results=st.one_of(
            st.none(),
            st.just([]),
            st.lists(execution_results(), max_size=5),
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_format_summary_footer_never_raises(self, results):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        result = format_summary_footer(results)
        assert isinstance(result, str)
        assert len(result) > 0

    # ------------------------------------------------------------------
    # compute_state_diff: resilience to None / non-dict / empty dicts
    # ------------------------------------------------------------------

    @given(
        before=st.one_of(st.none(), st.just({}), state_dicts),
        after=st.one_of(st.none(), st.just({}), state_dicts),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_compute_state_diff_never_raises(self, before, after):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        result = compute_state_diff(before, after)
        assert result is None or isinstance(result, str)

    # ------------------------------------------------------------------
    # build_llm_prompt: resilience to None / empty inputs
    # ------------------------------------------------------------------

    @given(
        intent=st.one_of(st.none(), st.just(""), safe_text),
        actions=st.one_of(st.none(), st.just([]), st.lists(network_actions(), max_size=3)),
        results=st.one_of(st.none(), st.just([]), st.lists(execution_results(), max_size=3)),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_build_llm_prompt_never_raises(self, intent, actions, results):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        result = build_llm_prompt(intent, actions, results)
        assert isinstance(result, str)
        assert len(result) > 0

    # ------------------------------------------------------------------
    # format_action_detail: resilience to arbitrary action/result combos
    # ------------------------------------------------------------------

    @given(pair=action_result_pairs())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_format_action_detail_never_raises(self, pair):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        action, result = pair
        output = format_action_detail(action, result)
        assert isinstance(output, str)
        assert len(output) > 0

    # ------------------------------------------------------------------
    # generate_summary: output is always a valid non-empty string
    # regardless of how extreme the inputs are
    # ------------------------------------------------------------------

    @given(
        intent=st.one_of(st.none(), st.just(""), st.text(min_size=0, max_size=200)),
        confidence=st.one_of(
            st.none(),
            st.floats(allow_nan=False, allow_infinity=False),
        ),
        llm_summary=st.one_of(st.none(), st.just(""), st.text(min_size=0, max_size=200)),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_generate_summary_extreme_scalars(self, intent, confidence, llm_summary):
        # Feature: network-change-summary, Property 6: Resilience to malformed inputs
        result = generate_summary(
            intent_text=intent,
            confidence=confidence,
            actions=[],
            results=[],
            llm_summary=llm_summary,
        )
        assert isinstance(result, str)
        assert len(result) > 0
