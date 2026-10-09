"""
Usage Evaluator & Deal Ranker

Parses consolidated_usage.csv to obtain current rates and average daily usage for Electricity and Gas,
and evaluates and ranks scraped Finder energy deals to select the top deals based on:
  1. Cashback / sign-up bonus credits
  2. Better daily supply charge
  3. Better usage charge
  4. Total estimated annual savings
"""

import csv
import os
import re
from datetime import datetime
import structlog
from typing import Dict, Any, List, Tuple
from src.config import CONSOLIDATED_CSV_PATH
from src.models import EnergyDealItem

logger = structlog.get_logger()


def _parse_row_date(row: Dict[str, str]) -> datetime:
    """Attempts to parse bill dates to order records chronologically."""
    for key in ("Period End", "Period Start", "Issue Date"):
        val = (row.get(key) or "").strip()
        if not val:
            continue
        cleaned = val.replace(" ", "")
        for fmt in ("%d-%b-%Y", "%d%b%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                pass
    return datetime.min


def load_current_usage_metrics(csv_path: str = str(CONSOLIDATED_CSV_PATH)) -> Dict[str, Any]:
    """
    Parses consolidated_usage.csv and extracts the latest rates and average daily usage.
    Returns a dictionary containing electricity and gas baseline metrics.
    """
    metrics = {
        "electricity": {
            "latest_provider": None,
            "latest_usage_rate": 0.0,
            "latest_daily_supply_rate": 0.0,
            "avg_daily_usage_kwh": 7.65,
            "annual_usage_kwh": 2792.25,
            "estimated_annual_cost": 0.0,
        },
        "gas": {
            "latest_provider": None,
            "latest_usage_rate": 0.0,
            "latest_daily_supply_rate": 0.0,
            "avg_daily_usage_mj": 54.84,
            "annual_usage_mj": 20016.60,
            "estimated_annual_cost": 0.0,
        }
    }

    if not os.path.exists(csv_path):
        logger.warning("Consolidated usage CSV not found at path", path=csv_path)
        return metrics

    try:
        elec_rows = []
        gas_rows = []

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                utility = row.get("Utility", "").strip().lower()
                if utility == "electricity":
                    elec_rows.append(row)
                elif utility == "gas":
                    gas_rows.append(row)

        # Sort chronologically by period/issue date so the latest bill is truly the latest
        elec_rows.sort(key=_parse_row_date)
        gas_rows.sort(key=_parse_row_date)

        # Process Electricity (latest row)
        if elec_rows:
            latest_elec = elec_rows[-1]
            metrics["electricity"]["latest_provider"] = latest_elec.get("Provider")
            try:
                metrics["electricity"]["latest_usage_rate"] = float(latest_elec.get("Usage Rate ($/unit)", 0) or 0)
                metrics["electricity"]["latest_daily_supply_rate"] = float(latest_elec.get("Daily Supply Rate ($/day)", 0) or 0)
            except ValueError:
                pass

            daily_usages = []
            for r in elec_rows:
                try:
                    val = float(r.get("Avg Daily Usage (kWh/day)", 0) or 0)
                    if val > 0:
                        daily_usages.append(val)
                except ValueError:
                    pass
            if daily_usages:
                avg_kwh = sum(daily_usages) / len(daily_usages)
                metrics["electricity"]["avg_daily_usage_kwh"] = avg_kwh
                metrics["electricity"]["annual_usage_kwh"] = avg_kwh * 365.0

            annual_kwh = metrics["electricity"]["annual_usage_kwh"]
            u_rate = metrics["electricity"]["latest_usage_rate"]
            s_rate = metrics["electricity"]["latest_daily_supply_rate"]
            metrics["electricity"]["estimated_annual_cost"] = (annual_kwh * u_rate) + (s_rate * 365.0)

        # Process Gas (latest row)
        if gas_rows:
            latest_gas = gas_rows[-1]
            metrics["gas"]["latest_provider"] = latest_gas.get("Provider")
            try:
                metrics["gas"]["latest_usage_rate"] = float(latest_gas.get("Usage Rate ($/unit)", 0) or 0)
                metrics["gas"]["latest_daily_supply_rate"] = float(latest_gas.get("Daily Supply Rate ($/day)", 0) or 0)
            except ValueError:
                pass

            daily_usages_gas = []
            for r in gas_rows:
                try:
                    val = float(r.get("Avg Daily Usage (MJ/day)", 0) or 0)
                    if val > 0:
                        daily_usages_gas.append(val)
                except ValueError:
                    pass
            if daily_usages_gas:
                avg_mj = sum(daily_usages_gas) / len(daily_usages_gas)
                metrics["gas"]["avg_daily_usage_mj"] = avg_mj
                metrics["gas"]["annual_usage_mj"] = avg_mj * 365.0

            annual_mj = metrics["gas"]["annual_usage_mj"]
            u_rate_gas = metrics["gas"]["latest_usage_rate"]
            s_rate_gas = metrics["gas"]["latest_daily_supply_rate"]
            metrics["gas"]["estimated_annual_cost"] = (annual_mj * u_rate_gas) + (s_rate_gas * 365.0)

        logger.info("Loaded current usage baseline metrics from CSV", metrics=metrics)

    except Exception as e:
        logger.error("Failed to parse consolidated usage CSV", error=str(e))

    return metrics


def evaluate_deal(deal: EnergyDealItem, baseline: Dict[str, Any]) -> Tuple[bool, str, float, Dict[str, bool]]:
    """
    Evaluates an EnergyDealItem against baseline usage rates.
    Returns:
        (is_better_deal: bool, evaluation_reason: str, estimated_annual_savings: float, criteria_matched: dict)
    """
    utility_key = "electricity" if "gas" not in deal.utility.lower() else "gas"
    base_info = baseline.get(utility_key, {})

    base_provider = base_info.get("latest_provider", "Current Provider")
    base_u_rate = base_info.get("latest_usage_rate", 0.0)
    base_s_rate = base_info.get("latest_daily_supply_rate", 0.0)
    base_annual_cost = base_info.get("estimated_annual_cost", 0.0)

    has_cashback = False
    cashback_amount = 0.0
    better_supply_charge = False
    better_usage_charge = False
    savings = 0.0

    # 1. Check for cashback / bonus credits using specific phrases (avoiding false positives like 'credit card fee')
    all_text = f"{deal.plan_name} {' '.join(deal.features)} {deal.raw_summary or ''}".lower()
    bonus_patterns = [
        r"\bcashback\b",
        r"\bbill credit\b",
        r"\bsign[\s-]?up credit\b",
        r"\bwelcome credit\b",
        r"\bwelcome bonus\b",
        r"\bgift card\b",
        r"\bbonus credit\b",
        r"\$\d+\s*(?:credit|bonus|cashback|off first bill)"
    ]
    if any(re.search(pat, all_text) for pat in bonus_patterns):
        has_cashback = True
        m_amt = re.search(r"\$(\d+(?:\.\d{2})?)\s*(?:credit|bonus|cashback|gift card|off)", all_text)
        if m_amt:
            try:
                cashback_amount = float(m_amt.group(1))
            except ValueError:
                cashback_amount = 50.0
        else:
            cashback_amount = 50.0

    # Normalize rates (if expressed in cents, convert to dollars)
    deal_u_rate = deal.usage_rate
    if deal_u_rate:
        # Australian gas usage is typically 2.0c-5.0c/MJ ($0.02-$0.05/MJ). If > 0.50, it is quoted in cents.
        # Electricity usage is typically 20c-45c/kWh ($0.20-$0.45/kWh). If > 1.0, it is quoted in cents.
        if utility_key == "gas" and deal_u_rate > 0.50:
            deal_u_rate = deal_u_rate / 100.0
        elif utility_key == "electricity" and deal_u_rate > 1.0:
            deal_u_rate = deal_u_rate / 100.0

    deal_s_rate = deal.daily_supply_rate
    if deal_s_rate and deal_s_rate > 5.0:
        # Daily supply rate is typically 90c-180c/day ($0.90-$1.80/day). If > 5.0, it is in cents/day.
        deal_s_rate = deal_s_rate / 100.0

    # 2. Check supply charge & usage charge rates
    if deal_s_rate and base_s_rate > 0:
        if deal_s_rate < base_s_rate:
            better_supply_charge = True

    if deal_u_rate and base_u_rate > 0:
        if deal_u_rate < base_u_rate:
            better_usage_charge = True

    # 3. Calculate annual savings
    if deal_u_rate and deal_s_rate:
        annual_usage = base_info.get("annual_usage_kwh", 2792.25) if utility_key == "electricity" else base_info.get("annual_usage_mj", 20016.60)
        deal_annual_cost = (annual_usage * deal_u_rate) + (deal_s_rate * 365.0)
        savings = base_annual_cost - deal_annual_cost
    elif deal.estimated_annual_cost and base_annual_cost > 0:
        savings = base_annual_cost - deal.estimated_annual_cost
    elif deal.reference_price_difference and base_annual_cost > 0:
        ref_text = deal.reference_price_difference.lower()
        m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", ref_text)
        if m_pct and ("less" in ref_text or "below" in ref_text or "off" in ref_text):
            pct = float(m_pct.group(1)) / 100.0
            savings = base_annual_cost * pct

    if has_cashback and cashback_amount > 0:
        savings += cashback_amount

    criteria = {
        "has_cashback": has_cashback,
        "better_supply_charge": better_supply_charge,
        "better_usage_charge": better_usage_charge,
    }

    reasons = []
    if has_cashback:
        reasons.append(f"Includes ${cashback_amount:.0f} Cashback/Credit" if cashback_amount > 0 else "Includes Cashback/Credit")
    if better_supply_charge and deal_s_rate and base_s_rate > 0:
        reasons.append(f"Lower Supply Rate (${deal_s_rate:.4f}/day vs ${base_s_rate:.4f}/day)")
    if better_usage_charge and deal_u_rate and base_u_rate > 0:
        reasons.append(f"Lower Usage Rate (${deal_u_rate:.4f}/unit vs ${base_u_rate:.4f}/unit)")
    if savings > 0:
        reasons.append(f"Est. Savings: ~${savings:.2f}/yr")

    # A deal qualifies if it produces net savings or offers strictly lower rates across both usage & supply
    is_better = (savings > 10.0) or (has_cashback and savings >= 0.0) or (better_supply_charge and better_usage_charge)
    reason_str = "; ".join(reasons) if reasons else f"Rates comparable to current {base_provider} baseline."

    return is_better, reason_str, round(savings, 2), criteria


def select_top_deals(deals: List[EnergyDealItem], baseline: Dict[str, Any], top_n: int = 3) -> List[Tuple[EnergyDealItem, str, float]]:
    """
    Evaluates, ranks, and returns the top N deals based on cashback, better rates, and annual savings.
    Returns list of tuples: (EnergyDealItem, reason_string, estimated_savings)
    """
    evaluated = []

    for deal in deals:
        is_better, reason, savings, criteria = evaluate_deal(deal, baseline)
        if is_better and savings >= 0:
            score = savings
            if criteria["has_cashback"]:
                score += 30.0
            if criteria["better_usage_charge"]:
                score += 20.0
            if criteria["better_supply_charge"]:
                score += 20.0

            evaluated.append((deal, reason, savings, score))

    evaluated.sort(key=lambda x: x[3], reverse=True)
    top_deals = [(item[0], item[1], item[2]) for item in evaluated[:top_n]]
    logger.info("Selected top deals", count=len(top_deals), requested_top_n=top_n)
    return top_deals
