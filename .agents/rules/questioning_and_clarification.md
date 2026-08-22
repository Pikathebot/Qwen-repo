# Questioning & Clarification Protocol (/grill-me Style)

Whenever there is a need to clarify requirements, resolve ambiguity, or decide between architectural/design choices:

## 1. Codebase First
- Before asking the user any question, thoroughly inspect the codebase, configs, and documentation.
- If an answer can be determined from existing code or project conventions, do not ask the user.

## 2. Structured Interactive Tooling (`ask_question`)
- Always use the `ask_question` tool to present questions interactively.
- Do not dump bullet-point lists of questions into standard markdown responses unless providing an implementation plan artifact.
- Provide structured, user-phrased options with a recommended answer listed first (prefixed with `(Recommended)`).

## 3. Sequential Decision Tree Exploration
- Ask questions **one at a time** (or one cohesive set of dependent decisions) to walk down each branch of the design tree.
- Resolve dependencies between decisions one-by-one before proceeding to subsequent questions.
- For each option, clearly explain the tradeoffs and context when appropriate.
