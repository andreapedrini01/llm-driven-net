# Bugfix Requirements Document

## Introduction

When the confidence score is above the `RULE_BASED_CONFIDENCE_THRESHOLD` (0.80), the rule-based engine runs but may produce only generic or empty actions, causing a fallback to ChatGPT. The log message in the fallback path incorrectly prints `confidence X.XX < 0.8`, even though the confidence is actually >= 0.80. The fallback occurred due to poor rule-based results, not low confidence. This misleading log output confuses operators monitoring the system.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN confidence >= RULE_BASED_CONFIDENCE_THRESHOLD (0.80) AND the rule-based engine produces only generic CONFIG_CHANGE actions (or no actions) AND the system falls back to ChatGPT THEN the system prints a log message stating `confidence X.XX < 0.8`, which is factually incorrect because the confidence is not below the threshold.

1.2 WHEN confidence >= RULE_BASED_CONFIDENCE_THRESHOLD (0.80) AND the rule-based engine produces no actions AND the system falls back to ChatGPT THEN the system prints the same misleading `confidence X.XX < 0.8` message, misrepresenting the reason for the fallback.

### Expected Behavior (Correct)

2.1 WHEN confidence >= RULE_BASED_CONFIDENCE_THRESHOLD (0.80) AND the rule-based engine produces only generic CONFIG_CHANGE actions AND the system falls back to ChatGPT THEN the system SHALL print a log message that accurately indicates the fallback is due to insufficient rule-based results (e.g., `confidence X.XX >= 0.8 but rule-based produced only generic actions, falling back to ChatGPT`).

2.2 WHEN confidence >= RULE_BASED_CONFIDENCE_THRESHOLD (0.80) AND the rule-based engine produces no actions AND the system falls back to ChatGPT THEN the system SHALL print a log message that accurately indicates the fallback is due to no rule-based results (e.g., `confidence X.XX >= 0.8 but rule-based produced no actions, falling back to ChatGPT`).

### Unchanged Behavior (Regression Prevention)

3.1 WHEN confidence < RULE_BASED_CONFIDENCE_THRESHOLD (0.80) THEN the system SHALL CONTINUE TO use ChatGPT for action generation and print the existing log message indicating confidence is below the threshold.

3.2 WHEN confidence >= RULE_BASED_CONFIDENCE_THRESHOLD (0.80) AND the rule-based engine produces specific, useful actions (FLOW_MOD, SLICE_CREATE, or non-generic CONFIG_CHANGE) THEN the system SHALL CONTINUE TO use the rule-based actions without falling back to ChatGPT, and log the rule-based success message as before.
