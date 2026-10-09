"""
Energy Monitor Orchestrator

Main script that orchestrates reading historical/current energy rates, scanning comparison sites
(configured dynamically in config.yaml) via Agno Firecrawl agent, evaluating deals against current rates,
selecting top deals, and notifying Slack channel.
"""

import sys
import structlog
from typing import List

from src.config import (
    validate_env,
    SLACK_WEBHOOK_URL,
    CONSOLIDATED_CSV_PATH,
    TARGET_SLACK_CHANNEL,
    SCRAPE_TARGETS,
    HOUSEHOLD_PROFILE
)
from src.evaluators.usage_evaluator import load_current_usage_metrics, select_top_deals
from src.agents.energy_deal_agent import create_energy_agent, extract_energy_deals
from src.models import EnergyDealItem
from src.notifiers.slack_notifier import (
    load_seen_deals,
    save_seen_deals,
    send_slack_top_deal,
    send_slack_top_summary
)

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()


def main():
    logger.info("Starting Energy Monitor Scan Task...")

    # 1. Read current usage and rates baseline from CSV
    baseline = load_current_usage_metrics(str(CONSOLIDATED_CSV_PATH))
    logger.info("Baseline usage metrics loaded", baseline=baseline)

    # 2. Check API keys and environment
    try:
        validate_env()
    except ValueError as e:
        logger.error("Environment validation failed", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    logger.info(
        "Household Profile loaded from .env",
        address=HOUSEHOLD_PROFILE.address,
        electricity_usage=HOUSEHOLD_PROFILE.electricity_usage,
        gas_usage=HOUSEHOLD_PROFILE.gas_usage,
        has_solar=HOUSEHOLD_PROFILE.has_solar
    )

    # 3. Create generic Agno Agent and scrape configured targets from config.yaml
    extracted_deals: List[EnergyDealItem] = []
    try:
        agent = create_energy_agent()
        for target in SCRAPE_TARGETS:
            target_name = target.get("name", "Site")
            target_url = target.get("url")
            target_prompt = target.get("prompt")
            logger.info("Scanning comparison target", name=target_name, url=target_url)

            site_deals = extract_energy_deals(
                agent=agent,
                target_url=target_url,
                prompt=target_prompt,
                profile=HOUSEHOLD_PROFILE
            )
            logger.info("Scanned target completed", name=target_name, deals_found=len(site_deals))
            extracted_deals.extend(site_deals)

        logger.info("Total extracted energy deals across all targets", total_count=len(extracted_deals))
    except Exception as e:
        logger.error("Failed to run Agno Firecrawl agent", error=str(e))
        sys.exit(1)

    # 4. Evaluate and select Top deals
    top_deals = select_top_deals(extracted_deals, baseline, top_n=3)

    seen_deals = load_seen_deals()

    # 5. Notify Slack with Top Deals
    for rank, (deal, reason, savings) in enumerate(top_deals, start=1):
        deal_key = f"{deal.provider}:{deal.plan_name}:{deal.utility}".lower().replace(" ", "_")
        logger.info("Top Deal Selected", rank=rank, provider=deal.provider, plan=deal.plan_name, savings=savings, reason=reason)

        if SLACK_WEBHOOK_URL:
            send_slack_top_deal(SLACK_WEBHOOK_URL, deal, rank=rank, reason=reason, savings=savings, channel=TARGET_SLACK_CHANNEL)
            seen_deals.add(deal_key)
        else:
            logger.warning("SLACK_WEBHOOK_URL not set; skipping Slack alert", rank=rank, deal=deal.model_dump())

    save_seen_deals(seen_deals)

    # 6. Send top deals summary banner to Slack
    if SLACK_WEBHOOK_URL and top_deals:
        send_slack_top_summary(SLACK_WEBHOOK_URL, top_deals, baseline, channel=TARGET_SLACK_CHANNEL)

    print(f"\n✅ Scan complete! Scraped {len(extracted_deals)} total deal(s).")
    print(f"🏆 Selected Top {len(top_deals)} deal(s) based on cashback, lower rates, and annual savings.")
    for rank, (deal, reason, savings) in enumerate(top_deals, start=1):
        print(f"  #{rank}: {deal.provider} ({deal.utility}) — {deal.plan_name} | Est. Savings: ~${savings:.2f}/yr")
        print(f"      Why: {reason}")


if __name__ == "__main__":
    main()
