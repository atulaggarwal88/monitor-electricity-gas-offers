"""
Configuration and Environment Settings for Energy Monitor
"""

import os
from pathlib import Path
from typing import List, Dict, Any
import yaml
from dotenv import load_dotenv, find_dotenv

from src.models.household_profile import HouseholdProfile

# Base Directory of the Project (root folder)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file (prioritizing root .env)
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file, override=True)
else:
    load_dotenv(find_dotenv(usecwd=True), override=True)

# YAML Configuration File Path & Loader (checks config/config.yaml and root config.yaml)
CONFIG_YAML_PATH = BASE_DIR / "config" / "config.yaml"
if not CONFIG_YAML_PATH.exists():
    CONFIG_YAML_PATH = BASE_DIR / "config.yaml"

_yaml_config: Dict[str, Any] = {}
if CONFIG_YAML_PATH.exists():
    with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
        _yaml_config = yaml.safe_load(f) or {}

_slack_config = _yaml_config.get("slack", {}) or _yaml_config.get("notifiers", {}).get("slack", {})


def _to_abs_path(path_str: str | Path) -> Path:
    """Converts a relative path to an absolute Path resolved against BASE_DIR."""
    p = Path(path_str)
    if not p.is_absolute():
        p = BASE_DIR / p
    return p.resolve()


# Directory & File Paths (guaranteed absolute paths)
LANDING_DIR = _to_abs_path(os.getenv("LANDING_DIR", "landing"))
OUTPUT_DIR = _to_abs_path(os.getenv("OUTPUT_DIR", "build/output"))
CONSOLIDATED_CSV_PATH = _to_abs_path(_yaml_config.get("usage_csv_path", "build/output/consolidated_usage.csv"))
SEEN_DEALS_FILE = _to_abs_path(_slack_config.get("output_seen_file", "build/seen_energy_deals.json"))

# API Keys & Integration Settings
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Household / Property Profile loaded from .env
HOUSEHOLD_PROFILE = HouseholdProfile.from_env()

# Application Constants & Scraping Targets
DEFAULT_MODEL_ID = os.getenv("DEFAULT_MODEL_ID", _yaml_config.get("model_id", "gemini-3.5-flash"))
TARGET_SLACK_CHANNEL = os.getenv("TARGET_SLACK_CHANNEL", _slack_config.get("channel", "electricity-gas-deals"))

# Default URL and Prompt template
DEFAULT_WEBSITE_URL = _yaml_config.get(
    "website_url",
    "https://www.finder.com.au/energy"
)
DEFAULT_PROMPT_TEMPLATE = _yaml_config.get(
    "prompt",
    "Search and scrape electricity and gas plan comparison deals on {url} for address: {address}. Household profile: Electricity usage = {electricity_usage}, Gas usage = {gas_usage}, Solar panel = {has_solar}. Extract all available plan offers."
)

# Parsed Scrape Targets from config.yaml
def get_scrape_targets() -> List[Dict[str, str]]:
    """
    Returns the list of scrape targets configured in config.yaml.
    Falls back to single website_url and prompt if targets list is absent.
    """
    targets = _yaml_config.get("targets", [])
    if targets and isinstance(targets, list):
        parsed = []
        for t in targets:
            if isinstance(t, dict) and "url" in t:
                parsed.append({
                    "name": t.get("name", "EnergyComparisonSite"),
                    "url": t.get("url"),
                    "prompt": t.get("prompt", DEFAULT_PROMPT_TEMPLATE)
                })
        if parsed:
            return parsed

    return [{
        "name": "Default",
        "url": DEFAULT_WEBSITE_URL,
        "prompt": DEFAULT_PROMPT_TEMPLATE
    }]


SCRAPE_TARGETS = get_scrape_targets()


def validate_env() -> None:
    """Validates that all required environment variables are set."""
    missing = []
    if not os.getenv("GOOGLE_API_KEY"):
        missing.append("GOOGLE_API_KEY")
    if not os.getenv("FIRECRAWL_API_KEY"):
        missing.append("FIRECRAWL_API_KEY")

    if missing:
        missing_vars_str = " and ".join(missing) if len(missing) <= 2 else ", ".join(missing)
        raise ValueError(f"{missing_vars_str} must be set in environment.")
