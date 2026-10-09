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
import structlog
from typing import Dict, Any, List, Tuple
from src.config import CONSOLIDATED_CSV_PATH
from src.models import EnergyDealItem

logger = structlog.get_logger()


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

        # TODO: use pandas
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                utility = row.get("Utility", "").strip().lower()
                if utility == "electricity":
                    elec_rows.append(row)
                elif utility == "gas":
                    gas_rows.append(row)

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
    better_supply_charge = False
    better_usage_charge = False
    savings = 0.0

    # 1. Check for cashback / bonus credits
    all_text = f"{deal.plan_name} {' '.join(deal.features)} {deal.raw_summary or ''}".lower()
    cashback_keywords = ["cashback", "credit", "bonus", "gift card", "reward", "$50", "$100", "$150", "$200"]
    if any(kw in all_text for kw in cashback_keywords):
        has_cashback = True

    # Normalize rates (if expressed in cents, convert to dollars)
    deal_u_rate = deal.usage_rate
    if deal_u_rate and deal_u_rate > 5.0:
        deal_u_rate = deal_u_rate / 100.0

    deal_s_rate = deal.daily_supply_rate
    if deal_s_rate and deal_s_rate > 5.0:
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
        annual_usage = base_info.get("annual_usage_kwh", 2601.0) if utility_key == "electricity" else base_info.get("annual_usage_mj", 27842.0)
        deal_annual_cost = (annual_usage * deal_u_rate) + (deal_s_rate * 365.0)
        savings = base_annual_cost - deal_annual_cost
    elif deal.estimated_annual_cost and base_annual_cost > 0:
        savings = base_annual_cost - deal.estimated_annual_cost
    elif deal.reference_price_difference:
        ref_text = deal.reference_price_difference.lower()
        if "less than" in ref_text or "% off" in ref_text or "below" in ref_text:
            savings = 60.0 # TODO: check this

    if has_cashback:
        savings += 50.0 # TODO: check this

    criteria = {
        "has_cashback": has_cashback,
        "better_supply_charge": better_supply_charge,
        "better_usage_charge": better_usage_charge,
    }

    reasons = []
    if has_cashback:
        reasons.append("Includes Cashback/Bonus Credit")
    if better_supply_charge:
        reasons.append(f"Lower Supply Rate (${deal_s_rate:.4f}/day vs ${base_s_rate:.4f}/day)")
    if better_usage_charge:
        reasons.append(f"Lower Usage Rate (${deal_u_rate:.4f}/unit vs ${base_u_rate:.4f}/unit)")
    if savings > 0:
        reasons.append(f"Est. Savings: ~${savings:.2f}/yr")

    is_better = has_cashback or better_supply_charge or better_usage_charge or (savings > 20.0)
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
        if is_better:
            score = savings
            if criteria["has_cashback"]:
                score += 100.0
            if criteria["better_usage_charge"]:
                score += 50.0
            if criteria["better_supply_charge"]:
                score += 50.0

            evaluated.append((deal, reason, savings, score))

    evaluated.sort(key=lambda x: x[3], reverse=True)
    top_deals = [(item[0], item[1], item[2]) for item in evaluated[:top_n]]
    logger.info("Selected top deals", count=len(top_deals), requested_top_n=top_n)
    return top_deals
