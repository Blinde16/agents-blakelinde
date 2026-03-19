# Coding Standards

## 1. Python (Backend) Rules
- **Formatting**: `ruff` is the absolute source of truth.
- **Typing**: `mypy` is enforced globally. All functions, specifically Langchain Tools, must use typed Pydantic models for argument schemas. 
- **Async First**: All database calls, HTTP queries, and LLM inferences inside the LangGraph nodes must be strictly `async` to prevent blocking the FastAPI Uvicorn worker thread.
- **Secrets Management**: Secrets (`os.environ`) must be fetched at initialization in `config.py` avoiding scattering `getenv` calls deep into random function trees. 

## 2. TypeScript (Frontend) Rules
- **Environment**: Next.js 14 App Router.
- **Strictness**: `tsconfig.json` `strict: true`. No generic `any` types. Everything requires a `type` or `interface`.
- **Imports**: All frontend internal paths must use absolute imports mapped to `@/components` or `@/lib`.
- **UI Components**: Use tailwind-merge and `clsx` for dynamic class manipulation. Avoid arbitrary CSS files; keep it in Tailwind classes.

## 3. Tool Development
```python
from pydantic import BaseModel, Field

# 1. Provide rigorous descriptions for the LLM
class SpecificToolArgs(BaseModel):
    query: str = Field(description="The exact SQL table query parameter.")

# 2. Add the tool decorator
@tool("fetch_specific", args_schema=SpecificToolArgs)
async def fetch_specific_tool(query: str) -> str:
    """Provides crucial operational data..."""
    ...
```
- **Error Shielding**: If a Python tool function fails (Value Error, 500 error from external API), do NOT raise the exception up to LangGraph. Trap it with a try/catch, and return `{"error": "Failed to connect to provider, reason X"}` as a string. The LLM must be given a chance to recover or explain the failure.
