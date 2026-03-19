# Repository Structure

The architecture dictates a strict separation of concerns, managed via monorepo layout. 

```text
/
├── /web                        # Next.js Application
│   ├── /app                    # App Router pages and API proxy endpoints
│   ├── /components             # Shadcn / UI action cards and chat bubbles
│   ├── /lib                    # Supabase JS clients, Clerk wrappers, Zustand store
│   └── package.json            
│
├── /agent                      # Python Execution Layer
│   ├── /prompts                # Markdown system prompts
│   ├── /src
│   │   ├── /api                # FastAPI routes and the Vapi Webhook Adapter
│   │   ├── /graph              # The primary Agno definitions (Lead Router, specialist agents)
│   │   ├── /tools              # Atomic Hubspot, Notion, and Postgres tool definitions
│   │   ├── main.py             # Uvicorn entrypoint
│   │   └── config.py           # Environment secrets validator
│   ├── pyproject.toml          # Uv / Poetry dependency mapping
│   └── Dockerfile              # Always-on deployment wrapper
│
├── /docs                       # Internal engineering documentation
│
├── /supabase                   
│   ├── /migrations             # Explicit .sql schema files (users, approvals)
│   └── config.toml
│
├── .cursorrules                # Context constraints for AI development tools
├── STYLEGUIDE.md               
├── CONTRIBUTING.md
└── package.json                # Turborepo / Monorepo build orchestrator (optional)
```
