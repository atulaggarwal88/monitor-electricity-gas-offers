"""
Unit tests for usage_evaluator and deal ranking logic.
"""

import unittest
from src.models import EnergyDealItem
from src.evaluators.usage_evaluator import evaluate_deal, select_top_deals


class TestUsageEvaluator(unittest.TestCase):

    def setUp(self):
        self.baseline = {
            "electricity": {
                "latest_provider": "EnergyAustralia",
                "latest_usage_rate": 0.28,
                "latest_daily_supply_rate": 1.20,
                "avg_daily_usage_kwh": 8.0,
                "annual_usage_kwh": 2920.0,
                "estimated_annual_cost": (2920.0 * 0.28) + (1.20 * 365.0), # 817.6 + 438 = 1255.6
            },
            "gas": {
                "latest_provider": "GloBird",
                "latest_usage_rate": 0.030,
                "latest_daily_supply_rate": 1.10,
                "avg_daily_usage_mj": 50.0,
                "annual_usage_mj": 18250.0,
                "estimated_annual_cost": (18250.0 * 0.030) + (1.10 * 365.0), # 547.5 + 401.5 = 949.0
            }
        }

    def test_gas_rate_normalization_in_cents(self):
        """Gas rate given in cents (e.g. 2.6c/MJ) must NOT be interpreted as $2.60/MJ."""
        deal = EnergyDealItem(
            provider="Origin",
            plan_name="Advantage Gas",
            utility="Gas",
            usage_rate=2.6, # 2.6 cents / MJ
            daily_supply_rate=1.00, # $1.00/day
            features=[]
        )
        is_better, reason, savings, criteria = evaluate_deal(deal, self.baseline)
        # Baseline gas annual cost = 949.0
        # Deal annual cost should be: (18250 * 0.026) + (1.00 * 365) = 474.5 + 365 = 839.5
        # Expected savings = 949.0 - 839.5 = 109.5
        self.assertTrue(is_better)
        self.assertAlmostEqual(savings, 109.5, delta=5.0)
        self.assertTrue(criteria["better_usage_charge"])

    def test_electricity_rate_normalization_in_cents(self):
        """Electricity rate in cents (e.g. 25.0c/kWh) should be converted to $0.25/kWh."""
        deal = EnergyDealItem(
            provider="OVO",
            plan_name="The One Plan",
            utility="Electricity",
            usage_rate=25.0, # 25 cents/kWh
            daily_supply_rate=110.0, # 110 cents/day
            features=[]
        )
        is_better, reason, savings, criteria = evaluate_deal(deal, self.baseline)
        # Expected deal: 0.25 $/kWh and 1.10 $/day
        # Baseline = 1255.6
        # Deal = (2920 * 0.25) + (1.10 * 365) = 730 + 401.5 = 1131.5
        # Savings = ~124.1
        self.assertTrue(is_better)
        self.assertAlmostEqual(savings, 124.1, delta=5.0)
        self.assertTrue(criteria["better_usage_charge"])
        self.assertTrue(criteria["better_supply_charge"])

    def test_cashback_keyword_filter(self):
        """Generic mention of 'credit card surcharge' or 'no credit check' should NOT count as cashback."""
        deal = EnergyDealItem(
            provider="BadDeal",
            plan_name="Expensive Plan",
            utility="Electricity",
            usage_rate=0.40, # expensive
            daily_supply_rate=2.00, # expensive
            features=["1% credit card fee applies", "credit check required"]
        )
        is_better, reason, savings, criteria = evaluate_deal(deal, self.baseline)
        self.assertFalse(criteria["has_cashback"], "Credit card fee should not trigger cashback")
        self.assertFalse(is_better, "More expensive plan should not be marked as better")

    def test_real_welcome_credit_detected(self):
        """Explicit sign-up bonus or bill credit should be recognized."""
        deal = EnergyDealItem(
            provider="GoodProvider",
            plan_name="Solar Saver",
            utility="Electricity",
            usage_rate=0.27,
            daily_supply_rate=1.15,
            features=["$100 bill credit on first bill", "No lock-in contract"]
        )
        is_better, reason, savings, criteria = evaluate_deal(deal, self.baseline)
        self.assertTrue(criteria["has_cashback"])
        self.assertTrue(is_better)


if __name__ == "__main__":
    unittest.main()
