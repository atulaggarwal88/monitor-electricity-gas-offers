"""
Unit tests for slack_notifier, deduplication, and PII protection.
"""

import unittest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock
from src.models import EnergyDealItem, HouseholdProfile
from src.notifiers.slack_notifier import (
    load_seen_deals,
    save_seen_deals,
    send_slack_top_deal,
    send_slack_top_summary,
    send_slack_message
)


class TestSlackNotifier(unittest.TestCase):

    def test_seen_deals_persistence(self):
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            temp_path = f.name

        try:
            seen = {"agl:value_saver:electricity", "origin:basic:gas"}
            save_seen_deals(seen, temp_path)
            loaded = load_seen_deals(temp_path)
            self.assertEqual(seen, loaded)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch("urllib.request.urlopen")
    def test_pii_redacted_in_deal_card(self, mock_urlopen):
        """Full residential street address should NOT appear in Slack payload."""
        mock_resp = MagicMock()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        profile = HouseholdProfile(
            address="123 Secret St, Suburbia VIC 3000",
            suburb="Suburbia",
            state="VIC",
            postcode="3000"
        )
        deal = EnergyDealItem(
            provider="AGL",
            plan_name="Saver",
            utility="Electricity",
            usage_rate=0.25,
            daily_supply_rate=1.10
        )

        send_slack_top_deal(
            webhook_url="https://hooks.slack.com/services/dummy",
            deal=deal,
            rank=1,
            reason="Lower rates",
            savings=100.0,
            channel="test-channel",
            profile=profile
        )

        self.assertTrue(mock_urlopen.called)
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        payload_str = json.dumps(payload)

        # Full street address should NOT be in the message
        self.assertNotIn("123 Secret St", payload_str)
        # Suburb or state can be shown
        self.assertIn("Suburbia", payload_str)

    @patch("urllib.request.urlopen")
    def test_pii_redacted_in_summary(self, mock_urlopen):
        """Full street address should NOT appear in summary banner."""
        mock_resp = MagicMock()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        profile = HouseholdProfile(
            address="123 Secret St, Suburbia VIC 3000",
            suburb="Suburbia",
            state="VIC",
            postcode="3000"
        )
        deal = EnergyDealItem(
            provider="AGL",
            plan_name="Saver",
            utility="Electricity"
        )

        send_slack_top_summary(
            webhook_url="https://hooks.slack.com/services/dummy",
            top_deals=[(deal, "Lower rates", 100.0)],
            baseline_info={},
            channel="test-channel",
            profile=profile
        )

        self.assertTrue(mock_urlopen.called)
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        payload_str = json.dumps(payload)

        self.assertNotIn("123 Secret St", payload_str)

    @patch("urllib.request.urlopen")
    def test_send_slack_message_has_timeout(self, mock_urlopen):
        """urlopen must be called with a timeout parameter to prevent hangs."""
        send_slack_message("https://hooks.slack.com/services/dummy", {"text": "hello"})
        self.assertTrue(mock_urlopen.called)
        kwargs = mock_urlopen.call_args[1]
        self.assertIn("timeout", kwargs)
        self.assertGreaterEqual(kwargs["timeout"], 5)


if __name__ == "__main__":
    unittest.main()
