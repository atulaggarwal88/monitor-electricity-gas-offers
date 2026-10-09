"""
Agno Energy Deals Agent with Firecrawl Integration

Defines and initializes a generic Agno AI Agent to scrape and extract electricity and gas deals
from any target comparison website (e.g., Finder.com.au, iSelect.com.au) using FirecrawlTools.
"""

import os
import json
import structlog
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Optional

# Fix google.genai.types import issue in recent google-genai versions for Agno
try:
    import google.genai.types
    if not hasattr(google.genai.types, "FileSearch"):
        google.genai.types.FileSearch = None
except Exception:
    pass

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.firecrawl import FirecrawlTools

from src.config import (
    DEFAULT_MODEL_ID,
    DEFAULT_WEBSITE_URL,
    DEFAULT_PROMPT_TEMPLATE,
    HOUSEHOLD_PROFILE,
    validate_env
)
from src.models import EnergyDealItem, EnergyDealList, HouseholdProfile

logger = structlog.get_logger()


def create_energy_agent(model_id: str = DEFAULT_MODEL_ID) -> Agent:
    """
    Initializes and returns a generic Agno Agent configured with Gemini and FirecrawlTools.
    Does not make exclusive direct API calls; uses FirecrawlTools within the agent.
    """
    validate_env()
    google_api_key = os.getenv("GOOGLE_API_KEY")
    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")

    agent = Agent(
        model=Gemini(
            id=model_id,
            api_key=google_api_key,
            timeout=120.0,
            retries=3,
            delay_between_retries=2,
            exponential_backoff=True,
        ),
        tools=[FirecrawlTools(api_key=firecrawl_api_key)],
        output_schema=EnergyDealList,
        instructions=[
            "You are an expert energy plan analyst, web scraper, and comparison monitoring agent.",
            "Use FirecrawlTools to scrape and extract energy comparison plans and deals from the specified website URL.",
            "Follow the user instructions and target household profile closely.",
            "Extract all available electricity and gas deals found on the website.",
            "For each plan, extract: provider name, plan name, utility type ('Electricity', 'Gas', or 'Dual Fuel'), estimated annual/monthly cost, reference price difference (e.g. '18% less than reference price'), usage rates ($/kWh or $/MJ), daily supply rates ($/day), solar feed-in tariff, signup/offer link, and key promotional features (e.g. cashback, credits, contract perks).",
            "Always output a structured EnergyDealList containing all extracted energy deal items."
        ],
        markdown=True
    )
    return agent


def extract_energy_deals(
    agent: Agent,
    target_url: Optional[str] = None,
    prompt: Optional[str] = None,
    profile: Optional[HouseholdProfile] = None,
    timeout_seconds: int = 150
) -> List[EnergyDealItem]:
    """
    Executes the agent generically with any target URL and prompt from config.yaml,
    interpolating household address and profile settings from .env.
    """
    url = target_url or DEFAULT_WEBSITE_URL
    raw_prompt = prompt or DEFAULT_PROMPT_TEMPLATE
    household = profile or HOUSEHOLD_PROFILE or HouseholdProfile.from_env()

    # Format the prompt dynamically with URL and household profile attributes
    formatted_prompt = household.format_prompt(raw_prompt, url=url)

    logger.info("Agent starting energy deal extraction", target_url=url, prompt=formatted_prompt)

    deals: List[EnergyDealItem] = []

    def _run_agent():
        return agent.run(formatted_prompt)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_agent)
            response = future.result(timeout=timeout_seconds)

        content = getattr(response, "content", None)

        if isinstance(content, EnergyDealList):
            deals = content.deals
        elif isinstance(content, str):
            cleaned_content = content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content.split("```json")[1].split("```")[0].strip()
            elif cleaned_content.startswith("```"):
                cleaned_content = cleaned_content.split("```")[1].split("```")[0].strip()
            try:
                parsed = json.loads(cleaned_content)
                if isinstance(parsed, dict) and "deals" in parsed:
                    for d in parsed["deals"]:
                        deals.append(EnergyDealItem(**d))
            except Exception:
                logger.warning("Failed to parse agent text response into JSON", raw_content=content[:200])

        logger.info("Agent completed energy deal extraction", target_url=url, deals_found=len(deals))

    except FutureTimeoutError:
        logger.error("Agent execution timed out", target_url=url, timeout_seconds=timeout_seconds)
    except Exception as e:
        logger.error("Error during agent execution", target_url=url, error=str(e))

    return deals
