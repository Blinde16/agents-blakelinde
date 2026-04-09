---
name: Finance Operations
description: Check client margins, YTD revenue, and parse financial spreadsheets.
---

# Finance Skill

This skill handles financial data checks, acting like the CFO layer.

## Usage

You have access to `scripts/finance.py` and `scripts/finance_staging.py` for executing queries and fetching metrics.

Since these are mostly read-only (fetching margins or revenue totals), you can execute these directly without explicit human approval for each query. Provide precise numbers and do not pad the data with fluff.
