# Changelog

All notable changes to `agents.blakelinde.com` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Pre-Alpha Planning Phase
### Added
- Complete comprehensive technical architecture documentation (`/docs`).
- Defined boundaries for MVP limiting tools to HubSpot, Notion, and Postgres queries.
- Defined asynchronous voice transport methodology parsing Vapi.ai events via Webhooks to avoid rigid API timeouts.
- Established strict decoupled architecture Next.js (Frontend UI) <-> Always-on Python FastAPI (Backend Graph).
- Defined LangGraph human-in-the-loop state pausing (`approval_gates` table mechanism).
- Initialized `.cursorrules` and monorepo structure maps.

---
*(Implementation begins next check-in)*
