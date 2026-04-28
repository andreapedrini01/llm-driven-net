# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Incorrect Fallback Log Message for High-Confidence Rule-Based Failure
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Generate confidence values in [0.80, 1.0] paired with generic/empty rule-based action lists to reproduce the bug deterministically
  - Bug Condition from design: `isBugCondition(input)` returns true when `input.confidence >= 0.80 AND NOT has_specific_actions`
  - Test that the log output from the `if not use_rule_based:` block does NOT contain `< {RULE_BASED_CONFIDENCE_THRESHOLD}` when confidence >= 0.80
  - Test that the log output accurately indicates the fallback is due to insufficient rule-based results
  - Mock `generate_actions_rule_based` to return only generic CONFIG_CHANGE actions or an empty list
  - Capture log output from the ChatGPT fallback path and assert it does not claim confidence is below threshold
  - Concrete cases: confidence=0.90 with generic actions, confidence=0.85 with empty actions, confidence=0.80 boundary
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists: log says "confidence X.XX < 0.8" when confidence is actually >= 0.80)
  - Document counterexamples found (e.g., "log contains 'confidence 0.90 < 0.8' when confidence is 0.90")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Low-Confidence and Successful Rule-Based Paths Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe on UNFIXED code: for confidence < 0.80, the log message format is `"Step 4: Generazione azioni con ChatGPT (confidence X.XX < 0.8)"` (or the English equivalent per the codebase)
  - Observe on UNFIXED code: for confidence >= 0.80 with specific actions (FLOW_MOD, SLICE_CREATE, non-generic CONFIG_CHANGE), the rule-based success path logs `"✓ N azioni generate (rule-based, senza ChatGPT)"`
  - Write property-based test: for all confidence values in [0.0, 0.80), the log message in the ChatGPT fallback block matches the original `confidence X.XX < {RULE_BASED_CONFIDENCE_THRESHOLD}` format exactly
  - Write property-based test: for all confidence values >= 0.80 with specific useful actions, the rule-based success path is taken and no ChatGPT fallback log is emitted
  - Mock `generate_actions_rule_based` appropriately for each scenario
  - Verify tests pass on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2_

- [x] 3. Fix incorrect fallback log message in main.py

  - [x] 3.1 Implement the fix
    - In `main.py` line 617, replace the unconditional `logger.info` with a conditional check on `intent_obj.confidence >= RULE_BASED_CONFIDENCE_THRESHOLD`
    - If confidence >= threshold: log `"Step 4: Generating actions with ChatGPT (confidence {confidence:.2f} >= {threshold}, but rule-based produced insufficient results)"`
    - If confidence < threshold: keep the existing log message `"Step 4: Generazione azioni con ChatGPT (confidence {confidence:.2f} < {threshold})"`
    - No other logic changes — the fix is isolated to the single log line
    - _Bug_Condition: isBugCondition(input) where input.confidence >= 0.80 AND NOT has_specific_actions_
    - _Expected_Behavior: Log message SHALL NOT contain `< {RULE_BASED_CONFIDENCE_THRESHOLD}` when confidence >= 0.80; SHALL accurately indicate rule-based fallback reason_
    - _Preservation: Low-confidence path (confidence < 0.80) log message unchanged; successful rule-based path unchanged; has_specific_actions logic unchanged; warning messages on lines 609-612 unchanged_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Accurate Fallback Message for High-Confidence Rule-Based Failure
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed — log no longer claims confidence < 0.8 when it is >= 0.80)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Low-Confidence and Successful Rule-Based Paths Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions — low-confidence log message and rule-based success path are unchanged)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
