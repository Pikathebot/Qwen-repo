# Strict Adherence to Stop-and-Review Checkpoints

## 1. Hard Stops are Non-Negotiable
- Whenever a prompt, implementation spec, or workflow phase specifies:
  - *"Propose the structure first and wait for review"*
  - *"Stop and show this part of the proposal before writing code"*
  - *"Obtain explicit approval before proceeding"*
- The agent **MUST** present the proposal / artifact and **STOP CALLING TOOLS IMMEDIATELY** to end its turn and wait for the user's explicit response.

## 2. No Combining Planning and Execution
- The agent must **NEVER** combine the proposal step and the implementation step into a single turn or autonomous run.
- Confidence in the solution or the fact that "the code will work out" is never a justification for bypassing a review gate.

## 3. Clear Resumption Trigger
- Implementation code may only be written after the user explicitly responds with approval (e.g., "Proceed", "Approved", "Go ahead").

## 4. Explicit Transparency for Scope Additions
- Any new parameters, thresholds, or architectural safety gates introduced during implementation (e.g., startup grace periods, extra threshold gates) must be explicitly highlighted in the implementation plan and walkthrough diffs rather than folded in silently.
