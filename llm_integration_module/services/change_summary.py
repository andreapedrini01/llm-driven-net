"""
Network Change Summary Module.

Generates and formats a structured summary of network changes
after intent execution. All formatting functions are pure functions
that never raise unhandled exceptions.
"""

import logging
from typing import Any, Dict, List, Optional

from llm_integration_module.models.actions import NetworkAction
from northbound_script_generator.action_processor import ExecutionResult, ExecutionStatus

logger = logging.getLogger("ChangeSummary")

SEPARATOR_HEAVY = "═" * 60
SEPARATOR_LIGHT_PREFIX = "── "
SEPARATOR_LIGHT_SUFFIX_CHAR = "─"


def _format_param_value(value: Any) -> str:
    """Format a parameter value for display."""
    if isinstance(value, dict):
        inner = ", ".join(f"{k}: {v}" for k, v in value.items())
        return "{" + inner + "}"
    if isinstance(value, list):
        return str(value)
    return str(value)


def _flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten a nested dictionary into dot-separated keys."""
    items: List[tuple] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries. override values take precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def format_action_detail(action: NetworkAction, result: ExecutionResult) -> str:
    """
    Format the detail of a single executed action.

    Includes action type, target, parameters (on success) or error (on failure),
    status icon (✓/✗) and duration.

    Args:
        action: The NetworkAction that was executed.
        result: The ExecutionResult from execution.

    Returns:
        Formatted multi-line string for this action.
    """
    try:
        action_type = getattr(action, "type", "unknown")
        if hasattr(action_type, "value"):
            action_type = action_type.value

        target = getattr(action, "target", "unknown")
        duration = getattr(result, "duration", 0.0) or 0.0
        status = getattr(result, "status", None)

        is_success = status == ExecutionStatus.SUCCESS

        icon = "✓" if is_success else "✗"
        action_id = getattr(action, "id", "?")

        lines = [f"  {icon} Action {action_id}: {action_type} on {target} ({duration:.2f}s)"]

        if is_success:
            params = getattr(action, "parameters", None)
            if params and isinstance(params, dict) and len(params) > 0:
                lines.append("    Parameters:")
                for key, value in params.items():
                    lines.append(f"      {key}: {_format_param_value(value)}")
        else:
            error = getattr(result, "error", None)
            if error:
                lines.append(f"    Error: {error}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in format_action_detail: {e}")
        return "  ✗ Error formatting action detail"


def compute_state_diff(
    state_before: Optional[Dict],
    state_after: Optional[Dict],
) -> Optional[str]:
    """
    Calculate and format differences between two network state dictionaries.

    Returns None if either state is None.
    Identifies added, removed and modified keys.

    Args:
        state_before: Network state before execution.
        state_after: Network state after execution.

    Returns:
        Formatted diff string, or None if diff cannot be computed.
    """
    try:
        if state_before is None or state_after is None:
            return None

        if not isinstance(state_before, dict) or not isinstance(state_after, dict):
            return None

        flat_before = _flatten_dict(state_before)
        flat_after = _flatten_dict(state_after)

        keys_before = set(flat_before.keys())
        keys_after = set(flat_after.keys())

        added = sorted(keys_after - keys_before)
        removed = sorted(keys_before - keys_after)
        common = sorted(keys_before & keys_after)

        modified = []
        for key in common:
            if flat_before[key] != flat_after[key]:
                modified.append(key)

        if not added and not removed and not modified:
            return None

        title = "Network State Diff"
        suffix_len = max(0, 60 - len(SEPARATOR_LIGHT_PREFIX) - len(title) - 1)
        header = f"{SEPARATOR_LIGHT_PREFIX}{title} {SEPARATOR_LIGHT_SUFFIX_CHAR * suffix_len}"

        lines = [header]
        for key in added:
            lines.append(f"  + {key}: {flat_after[key]}")
        for key in modified:
            lines.append(f"  ~ {key}: {flat_before[key]} → {flat_after[key]}")
        for key in removed:
            lines.append(f"  - {key}: (removed)")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in compute_state_diff: {e}")
        return None


def format_summary_header(
    intent_text: str,
    confidence: float,
    threshold: float = 0.8,
) -> str:
    """
    Format the summary header with original intent, mode and confidence.

    Args:
        intent_text: The original intent text.
        confidence: Confidence value (0.0 to 1.0).
        threshold: Threshold for rule-based vs LLM mode.

    Returns:
        Formatted header string.
    """
    try:
        if confidence is None:
            confidence = 0.0
        confidence = float(confidence)

        mode = "Rule-based" if confidence >= threshold else "LLM"

        lines = [
            SEPARATOR_HEAVY,
            "  NETWORK CHANGE SUMMARY",
            f'  Intent: "{intent_text or ""}"',
            f"  Mode: {mode} (confidence: {confidence:.2f})",
            SEPARATOR_HEAVY,
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in format_summary_header: {e}")
        return SEPARATOR_HEAVY + "\n  NETWORK CHANGE SUMMARY\n" + SEPARATOR_HEAVY


def format_summary_footer(results: List[ExecutionResult]) -> str:
    """
    Format the final summary with success/failure count and percentage.

    Args:
        results: List of ExecutionResult from action execution.

    Returns:
        Formatted footer string.
    """
    try:
        if not results:
            results = []

        total = len(results)
        successful = sum(
            1 for r in results
            if getattr(r, "status", None) == ExecutionStatus.SUCCESS
        )
        failed = total - successful
        percentage = (successful / total * 100) if total > 0 else 0.0

        lines = [
            SEPARATOR_HEAVY,
            f"  RESULT: {successful}/{total} actions completed ({percentage:.1f}%)",
            f"  Succeeded: {successful} | Failed: {failed}",
            SEPARATOR_HEAVY,
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in format_summary_footer: {e}")
        return SEPARATOR_HEAVY + "\n  RESULT: calculation error\n" + SEPARATOR_HEAVY


def generate_summary(
    intent_text: str,
    confidence: float,
    actions: List[NetworkAction],
    results: List[ExecutionResult],
    llm_summary: Optional[str] = None,
    threshold: float = 0.8,
) -> str:
    """
    Orchestration function that generates the complete change summary.

    Combines header, action details, state diff, footer and optional
    LLM summary section. Handles malformed inputs (None, empty lists,
    missing parameters) without raising exceptions.

    Args:
        intent_text: The original intent text.
        confidence: Confidence value (0.0 to 1.0).
        actions: List of NetworkAction executed.
        results: List of ExecutionResult from execution.
        llm_summary: Optional LLM-generated summary text.
        threshold: Threshold for rule-based vs LLM mode.

    Returns:
        Complete formatted summary string.
    """
    try:
        if actions is None:
            actions = []
        if results is None:
            results = []
        if confidence is None:
            confidence = 0.0

        sections = []

        # Header
        sections.append(format_summary_header(intent_text, confidence, threshold))
        sections.append("")

        # Action details
        action_map = {getattr(a, "id", None): a for a in actions}
        for i, result in enumerate(results):
            action_id = getattr(result, "action_id", None)
            action = action_map.get(action_id)
            if action is None and i < len(actions):
                action = actions[i]
            if action is not None:
                sections.append(format_action_detail(action, result))
                sections.append("")

        # State diff — aggregate from all results
        all_state_before: Dict[str, Any] = {}
        all_state_after: Dict[str, Any] = {}
        has_states = False
        for result in results:
            sb = getattr(result, "network_state_before", None)
            sa = getattr(result, "network_state_after", None)
            if isinstance(sb, dict):
                all_state_before = _deep_merge(all_state_before, sb)
                has_states = True
            if isinstance(sa, dict):
                all_state_after = _deep_merge(all_state_after, sa)
                has_states = True

        if has_states:
            diff = compute_state_diff(all_state_before, all_state_after)
            if diff is not None:
                sections.append(diff)
                sections.append("")

        # Footer
        sections.append(format_summary_footer(results))

        # LLM summary section
        if llm_summary:
            sections.append("")
            title = "LLM Summary"
            suffix_len = max(0, 60 - len(SEPARATOR_LIGHT_PREFIX) - len(title) - 1)
            header_line = f"{SEPARATOR_LIGHT_PREFIX}{title} {SEPARATOR_LIGHT_SUFFIX_CHAR * suffix_len}"
            footer_line = SEPARATOR_LIGHT_SUFFIX_CHAR * 60

            llm_lines = [header_line]
            for line in llm_summary.strip().splitlines():
                llm_lines.append(f"  {line}")
            llm_lines.append(footer_line)
            sections.append("\n".join(llm_lines))

        return "\n".join(sections)
    except Exception as e:
        logger.error(f"Error in generate_summary: {e}")
        return (
            SEPARATOR_HEAVY
            + "\n  NETWORK CHANGE SUMMARY\n"
            + "  Error generating summary\n"
            + SEPARATOR_HEAVY
        )


def build_llm_prompt(
    intent_text: str,
    actions: List[NetworkAction],
    results: List[ExecutionResult],
) -> str:
    """
    Build the prompt to send to ChatGPTClient.

    Contains the original intent, the type/target of each action,
    and the status of each execution result.

    Args:
        intent_text: The original intent text.
        actions: List of NetworkAction executed.
        results: List of ExecutionResult from execution.

    Returns:
        Prompt string for the ChatGPTClient.
    """
    lines = [
        "Summarize the following network changes in natural language.",
        "",
        f"Original intent: {intent_text or ''}",
        "",
        "Actions executed:",
    ]

    safe_actions = actions if actions else []
    safe_results = results if results else []

    for i, action in enumerate(safe_actions):
        action_type = getattr(action, "type", "unknown")
        if hasattr(action_type, "value"):
            action_type = action_type.value
        target = getattr(action, "target", "unknown")
        lines.append(f"  - Action {i + 1}: {action_type} on {target}")

    lines.append("")
    lines.append("Execution results:")

    for i, result in enumerate(safe_results):
        status = getattr(result, "status", None)
        status_str = status.value if hasattr(status, "value") else str(status)
        error = getattr(result, "error", None)
        entry = f"  - Result {i + 1}: {status_str}"
        if error:
            entry += f" (error: {error})"
        lines.append(entry)

    return "\n".join(lines)


async def generate_llm_summary(
    chatgpt_client: "ChatGPTClient",
    intent_text: str,
    actions: List[NetworkAction],
    results: List[ExecutionResult],
) -> Optional[str]:
    """
    Generate a natural-language summary via the LLM.

    Invokes the ChatGPTClient and returns the summary text,
    or None on any error. Never raises exceptions.

    Args:
        chatgpt_client: The ChatGPTClient instance.
        intent_text: The original intent text.
        actions: List of NetworkAction executed.
        results: List of ExecutionResult from execution.

    Returns:
        Summary text string, or None if generation failed.
    """
    try:
        prompt = build_llm_prompt(intent_text, actions, results)
        response = await chatgpt_client.generate_response(
            prompt=prompt,
            system_message="You are a network operations assistant. Provide a concise summary of the network changes described below.",
        )
        content = getattr(response, "content", None)
        if content and isinstance(content, str) and content.strip():
            return content.strip()
        return None
    except Exception as e:
        logger.warning(f"Failed to generate LLM summary: {e}")
        return None
