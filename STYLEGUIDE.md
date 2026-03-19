# Styleguide

## UI/UX Aesthetic Philosophy
The system provides a **Command-Line / High-End Tooling** aesthetic. It is not a friendly consumer chatbot.

1. **Colors**: Dark-mode enforced default. High contrast borders. Typography must be neutral and data-first (e.g., Inter, SF Pro, or JetBrains Mono for system outputs).
2. **Spacing**: Dense. Do not waste extensive mobile real estate with massive chat padding. Allow thumb-reachable access to the core chat input loop.
3. **Animations**: Minimal. Only use animations to indicate system load states (e.g. the skeleton or pulse effect when LangGraph is routing). Avoid bouncy, playful transitions.
4. **Action Cards**: Must instantly draw the eye away from regular text. Use strict color coding (e.g. subtle green/red bars for Approve/Reject status) to indicate state mutation boundaries.

## Architecture Philosophy
1. **Explicit > Autonomous**: It is better to fail and ask the user a clarifying question than to hallucinate a "magic" autonomous workflow.
2. **Safe Idling**: Long-running processes are expected. The default state for an ambiguous or dangerous mutation is "Paused/Pending Approval" (indefinitely).
3. **Inspectability**: Code should read sequentially. Do not use massive recursive wrapper patterns that obscure the LangGraph state edges. Name nodes explicitly (`CFO_Node`, `Ops_Node`) so LangSmith traces are instantly legible.
