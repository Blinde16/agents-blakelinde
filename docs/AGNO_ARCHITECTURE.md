# Agno AgentOS Architecture

## 1. Core Principles
The Agno AgentOS structure utilizes a **Multi-Agent Team** pattern. The application features a lead orchestration agent that strictly routes queries to an interconnected team of specialized agents, ensuring execution, persistence, and safe tool-calling.

## 2. Agent Orchestration Model
We utilize Agno's `Agent` definitions and memory models to manage the execution state. 

```python
from agno.agent import Agent
from agno.memory.db.postgres import PgMemoryDb
from agno.storage.agent.postgres import PgAgentStorage

# Standard memory setup using Supabase Postgres
db_url = "postgresql://postgres:...@...:5432/postgres"

agent_storage = PgAgentStorage(table_name="agent_storage", db_url=db_url)
agent_memory = PgMemoryDb(table_name="agent_memory", db_url=db_url)
```

## 3. Agent Definitions
- **`Lead_Router_Agent`**: Acts as an evaluator and delegator. Reviews user input and delegates the task to the appropriate specialist agent.
- **`CFO_Agent`, `CRO_Agent`, `CMO_Agent`, `Ops_Agent`**: The specialist agents. Each is explicitly provided with specialized system prompts and tightly bound tools.
- **`Tool_Handlers`**: Safe tools are executed instantly by the assigned agent. Unsafe, state-mutating tools require pausing the flow to request human approval.

## 4. Human-In-The-Loop (HITL) & Tool Logic
Because Agno does not use a node-based sequential graph, Human-in-the-Loop workflows for state-mutating tools are managed via **Custom Approval Tools**.
1. **START** ➔ `Lead_Router_Agent` receives input.
2. `Lead_Router` delegates to the target specialist.
3. The specialist determines the required action.
   - If a tool is strictly a read operation, the agent executes it immediately.
   - If a tool is a write operation (e.g., sending an email), the tool does NOT execute the action. Instead, the tool writes the payload to an `approval_gates` Postgres table with status `PENDING` and returns an internal memo to the agent to pause processing and await approval.
4. Next.js UI picks up the `PENDING` state and presents it to the user.
5. Upon user approval, the UI resumes the thread by communicating the approval status back to the agent via an explicit API `/resume` command, which allows the agent to finalize the execution.

## 5. Persistence
We use Agno's built-in **Postgres Memory and Storage Adapters**.
- **`PgMemoryDb` & `PgAgentStorage`**: Ties the session memory to Next.js `thread_id` records. Memory persists across interactions, ensuring the system can recall past operations and state-pending tool requests natively.

## 6. Observability
Visibility into the agent processing runs is achieved by utilizing standard Python logging in combination with Agno's built-in run monitoring capabilities.
