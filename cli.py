#!/usr/bin/env python3
import fire
import json
import asyncio
from dotenv import load_dotenv
load_dotenv()
from src.tools.registry import ToolRuntimeContext

# Import the actual skill scripts
from skills.finance.scripts import finance as raw_finance
from skills.hubspot.scripts import hubspot as raw_hubspot
# (Ignoring google_workspace and social for brevity/safety unless needed, but they work with the same pattern)

def _mock_ctx():
    return ToolRuntimeContext(thread_id="openclaw_session", db_url="", user_internal_id="local_openclaw_user")

class FinanceCLI:
    def margin(self, client_name: str):
        return raw_finance.client_margin(client_name)
    def revenue(self, timeframe: str):
        return raw_finance.revenue_summary(timeframe)

class HubSpotCLI:
    def read_deal(self, deal_name: str):
        return raw_hubspot.read_deal(deal_name)
    def update_stage(self, deal_id: str, new_stage: str):
        return raw_hubspot.update_deal_stage(deal_id, new_stage)

class OpenClawCLI:
    def __init__(self):
        self.finance = FinanceCLI()
        self.hubspot = HubSpotCLI()

if __name__ == "__main__":
    fire.Fire(OpenClawCLI)
