"""
Slack Notifier for Energy Deals

Sends formatted deal cards for top energy deals to Slack channel 'electricity-gas-deals' via Slack Webhook URL.
Tracks seen deals in build/seen_energy_deals.json to prevent duplicate alerts.
"""

import os
import json
import urllib.request
import structlog
from datetime import datetime
from typing import List, Tuple, Union, Set, Optional
from src.config import SEEN_DEALS_FILE, TARGET_SLACK_CHANNEL, HOUSEHOLD_PROFILE
from src.models import EnergyDealItem, HouseholdProfile

logger = structlog.get_logger()


def load_seen_deals(file_path: str = str(SEEN_DEALS_FILE)) -> Set[str]:
    """Loads a set of previously notified energy deal identifiers."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception as e:
            logger.warning("Could not load seen energy deals file", error=str(e))
    return set()


def save_seen_deals(seen_set: Set[str], file_path: str = str(SEEN_DEALS_FILE)) -> None:
    """Saves set of seen deal identifiers."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(list(seen_set), f, indent=2)
    except Exception as e:
        logger.error("Failed to save seen energy deals file", error=str(e))


def deal_to_dict(deal: Union[EnergyDealItem, dict]) -> dict:
    """Converts EnergyDealItem or dict into a dictionary."""
    if isinstance(deal, EnergyDealItem):
        return deal.model_dump()
    return deal


def send_slack_message(webhook_url: str, payload: dict) -> bool:
    """Helper to send JSON payload to Slack Webhook URL."""
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as resp:
            pass
        return True
    except Exception as e:
        logger.error("Failed to post message to Slack", error=str(e))
        return False


def send_slack_top_deal(
    webhook_url: str,
    deal: EnergyDealItem,
    rank: int,
    reason: str,
    savings: float,
    channel: str = TARGET_SLACK_CHANNEL,
    profile: Optional[HouseholdProfile] = None
) -> bool:
    """Sends a rich formatted deal card for a top-ranked energy deal to Slack channel."""
    household = profile or HOUSEHOLD_PROFILE
    d = deal_to_dict(deal)
    provider = d.get("provider", "Energy Provider")
    plan_name = d.get("plan_name", "Energy Plan")
    utility = d.get("utility", "Electricity")
    link = d.get("link") or "https://www.finder.com.au/energy"
    cost_str = f"${d['estimated_annual_cost']:.2f}/yr" if d.get("estimated_annual_cost") else "N/A"
    ref_diff = d.get("reference_price_difference") or "N/A"
    features_str = ", ".join(d.get("features", [])) if d.get("features") else "Standard plan"

    badge = "🥇 TOP #1 DEAL" if rank == 1 else ("🥈 TOP #2 DEAL" if rank == 2 else f"🥉 TOP #{rank} DEAL")
    header_icon = "⚡" if utility.lower() == "electricity" else "🔥"

    address_display = household.address if household and household.address else "Configured Property"
    solar_display = "Solar" if (household and household.has_solar) else "No Solar"
    usage_display = f"{household.electricity_usage} Elec / {household.gas_usage} Gas" if household else "Standard Usage"

    payload = {
        "channel": f"#{channel}",
        "text": f"{badge}: {header_icon} {provider} - {plan_name}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{badge}* {header_icon}\n*<{link}|{provider} — {plan_name}>*\n*Channel:* `#{channel}`"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Utility:* {utility}"},
                    {"type": "mrkdwn", "text": f"*Est. Annual Cost:* {cost_str}"},
                    {"type": "mrkdwn", "text": f"*Ref Price Diff:* {ref_diff}"},
                    {"type": "mrkdwn", "text": f"*Est. Value/Savings:* *~${savings:.2f}/year*"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Why it's a Top Deal:* {reason}\n*Key Features:* {features_str}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Scanned for {address_display} ({usage_display}, {solar_display}) • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                ]
            }
        ]
    }

    success = send_slack_message(webhook_url, payload)
    if success:
        logger.info("Slack top energy deal card sent successfully", rank=rank, provider=provider, plan=plan_name, channel=channel)
    return success


def send_slack_top_summary(
    webhook_url: str,
    top_deals: List[Tuple[EnergyDealItem, str, float]],
    baseline_info: dict,
    channel: str = TARGET_SLACK_CHANNEL,
    profile: Optional[HouseholdProfile] = None
) -> None:
    """Sends a summary banner of top deals to Slack."""
    household = profile or HOUSEHOLD_PROFILE
    elec_base = baseline_info.get("electricity", {})
    gas_base = baseline_info.get("gas", {})

    elec_provider = elec_base.get("latest_provider", "Current Provider")
    gas_provider = gas_base.get("latest_provider", "Current Provider")

    deal_summary_lines = []
    for rank, (deal, reason, savings) in enumerate(top_deals, start=1):
        deal_summary_lines.append(f"*{rank}. {deal.provider} ({deal.utility})* — {deal.plan_name} | Est. Savings: *~${savings:.2f}/yr*")

    deals_text = "\n".join(deal_summary_lines) if deal_summary_lines else "No better deals found than current baseline."
    address_display = household.address if household and household.address else "Configured Property"

    summary_text = (
        f"🏆 *Top {len(top_deals)} Energy Deals for {address_display}* (`#{channel}`)\n\n"
        f"{deals_text}\n\n"
        f"📊 *Current Baseline Rates ({elec_provider} / {gas_provider}):*\n"
        f"- Electricity: Usage `${elec_base.get('latest_usage_rate')}/kWh`, Supply `${elec_base.get('latest_daily_supply_rate')}/day`\n"
        f"- Gas: Usage `${gas_base.get('latest_usage_rate')}/MJ`, Supply `${gas_base.get('latest_daily_supply_rate')}/day`"
    )

    payload = {
        "channel": f"#{channel}",
        "text": f"🏆 Top {len(top_deals)} Energy Deals Summary (`#{channel}`)",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary_text
                }
            }
        ]
    }
    send_slack_message(webhook_url, payload)
