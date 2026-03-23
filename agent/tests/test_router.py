import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration.router import AGENT_IDS, RouteDecision, route_message


class RouteMessageTests(unittest.TestCase):
    """Keyword fallback only (no OpenAI)."""

    def setUp(self) -> None:
        self._env = patch.dict(os.environ, {"ROUTER_USE_LLM": "0"}, clear=False)
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()

    def test_routes_explicit_slash_command(self) -> None:
        decision = asyncio.run(route_message("/cfo show YTD revenue"))
        self.assertEqual(decision.target, "CFO")
        self.assertEqual(decision.normalized_message, "show YTD revenue")
        self.assertEqual(decision.active_agent, "Finance_Layer")

    def test_routes_sales_keywords_to_cro(self) -> None:
        decision = asyncio.run(route_message("move the Acme deal to closed won in HubSpot"))
        self.assertEqual(decision.target, "CRO")
        self.assertEqual(decision.active_agent, "Sales_Ops_Layer")

    def test_routes_cross_domain_keyword_priority_to_cfo(self) -> None:
        decision = asyncio.run(route_message("check margin and update the CRM stage"))
        self.assertEqual(decision.target, "CFO")
        self.assertEqual(decision.active_agent, "Finance_Layer")


class LLMRouterMockTests(unittest.TestCase):
    def test_llm_can_route_mixed_domain_to_ops(self) -> None:
        decision_obj = RouteDecision(
            target="OPS",
            confidence_score=0.88,
            reasoning="LLM router: finance + CRM mix → triage",
            normalized_message="check margin and update the CRM stage",
            active_agent=AGENT_IDS["OPS"],
        )
        with patch.dict(os.environ, {"ROUTER_USE_LLM": "1", "OPENAI_API_KEY": "sk-test"}, clear=False):
            with patch(
                "src.orchestration.router._llm_classify_route",
                new_callable=AsyncMock,
                return_value=decision_obj,
            ):
                decision = asyncio.run(route_message("check margin and update the CRM stage"))
        self.assertEqual(decision.target, "OPS")
        self.assertEqual(decision.active_agent, "Operations_Layer")


if __name__ == "__main__":
    unittest.main()
