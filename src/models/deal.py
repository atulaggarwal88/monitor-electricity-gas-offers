"""
Data models for Energy deal monitoring application.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class EnergyDealItem(BaseModel):
    provider: str = Field(description="Energy provider name, e.g. AGL, OVO Energy, EnergyAustralia, GloBird, Amber")
    plan_name: str = Field(description="Plan name or offer title")
    utility: str = Field(default="Electricity", description="Utility type: 'Electricity', 'Gas', or 'Dual Fuel'")
    estimated_annual_cost: Optional[float] = Field(default=None, description="Estimated total annual cost in AUD ($/year) if available")
    estimated_monthly_cost: Optional[float] = Field(default=None, description="Estimated monthly cost in AUD ($/month) if available")
    reference_price_difference: Optional[str] = Field(default=None, description="Percentage above/below reference price, e.g. '18% less than reference price'")
    usage_rate: Optional[float] = Field(default=None, description="Usage rate in $/kWh for electricity or $/MJ for gas if available")
    daily_supply_rate: Optional[float] = Field(default=None, description="Daily supply rate in $/day if available")
    solar_feed_in_tariff: Optional[float] = Field(default=None, description="Solar Feed-in Tariff in cents/kWh or $/kWh if available")
    link: str = Field(default="", description="Link or URL to sign up or view deal details")
    features: List[str] = Field(default_factory=list, description="Key features or contract details, e.g., 'No exit fees', 'Solar bonus', 'Cashback'")
    raw_summary: Optional[str] = Field(default=None, description="Brief overall summary of the deal")


class EnergyDealList(BaseModel):
    deals: List[EnergyDealItem] = Field(description="List of electricity and gas deals found on Finder")
