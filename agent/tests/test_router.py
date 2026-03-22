import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration.router import route_message


class RouteMessageTests(unittest.TestCase):
    def test_routes_explicit_slash_command(self):
        decision = route_message("/cfo show YTD revenue")
        self.assertEqual(decision.target, "CFO")
        self.assertEqual(decision.normalized_message, "show YTD revenue")
        self.assertEqual(decision.active_agent, "Finance_Layer")

    def test_routes_sales_keywords_to_cro(self):
        decision = route_message("move the Acme deal to closed won in HubSpot")
        self.assertEqual(decision.target, "CRO")
        self.assertEqual(decision.active_agent, "Sales_Ops_Layer")

    def test_routes_cross_domain_to_ops(self):
        decision = route_message("check margin and update the CRM stage")
        self.assertEqual(decision.target, "OPS")
        self.assertLess(decision.confidence_score, 0.5)


if __name__ == "__main__":
    unittest.main()
