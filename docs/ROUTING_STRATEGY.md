# Routing Strategy

Routing determines which functional layer handles the user's prompt. The MVP utilizes a hybrid approach: **Rules First, LLM Classifier Fallback**.

## 1. Rules-First Explicit Routing
System designers and users can bypass LLMs entirely for speed and precision by using text or interface triggers.
- **Slash Commands**: An input starting with `/cfo`, `/cro`, `/cmo`, or `/ops` completely bypasses the classifier phase. `active_agent` is set structurally via regex.
- **Context Routing**: If the user is viewing a "Pipeline" dashboard on the UI, the frontend appends metadata `{"context": "cro"}` indicating the default fallback.

## 2. LLM Classifier Routing
If no structural rule applies, the user input is parsed by the `Router_Node`.
- **Model**: `gpt-4o-mini` (fastest possible model).
- **Mechanism**: The model uses OpenAI's `response_format` (JSON / structured output) to guarantee it returns a predictable Enum.
- **Output Schema**:
  ```python
  class RouteDecision(BaseModel):
      target: Literal["CFO", "CRO", "CMO", "OPS"]
      confidence_score: float
      reasoning: str
  ```

## 3. Handling Ambiguity
If `confidence_score` is less than 0.85, or the request contains multiple unrelated requests (e.g., "What's my margin and also update the CRM"), the Router defaults to `OPS`.

## 4. "One Handoff Max" Strategy
Unlike complex autonomous agent swarms, elements in this graph are not allowed to continuously pass the ball back and forth trying to solve a puzzle.
- **Scenario**: User asks Ops for financial data.
- **Action**: Ops recognizes it needs Financials, triggers `escalation = 1`, and reroutes to CFO.
- **Scenario**: CFO receives reroute, but request is missing client name. CFO cannot ask Ops to go find it. 
- **Action**: CFO must directly output text to the user: "Specify the client name to retrieve margins." (Aborts further node hops).
