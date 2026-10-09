"""
Data model for Household / Property profile stored in environment variables.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field


class HouseholdProfile(BaseModel):
    """
    Household / Property profile information such as address and usage levels.
    Loaded strictly from environment variables or custom configuration at runtime.
    """
    address: str = Field(
        default="",
        description="Full street address including suburb, state, postcode"
    )
    suburb: Optional[str] = Field(default=None, description="Suburb name")
    state: Optional[str] = Field(default=None, description="State or Territory code (e.g., VIC, NSW, QLD)")
    postcode: Optional[str] = Field(default=None, description="Postal code")
    electricity_usage: str = Field(
        default="Medium",
        description="Electricity usage level: 'Low', 'Medium', or 'High'"
    )
    gas_usage: str = Field(
        default="Medium",
        description="Gas usage level: 'Low', 'Medium', or 'High'"
    )
    has_solar: bool = Field(
        default=True,
        description="Whether solar panels are installed on the property"
    )

    @property
    def safe_location(self) -> str:
        """Returns non-PII location string (suburb, state, postcode) for notifications/logs."""
        parts = [p for p in [self.suburb, self.state, self.postcode] if p]
        if parts:
            return ", ".join(parts) if len(parts) > 1 and self.suburb else " ".join(parts)
        if self.address:
            # Fall back to trying to extract suburb/state from trailing comma separated component
            address_parts = [p.strip() for p in self.address.split(",") if p.strip()]
            if len(address_parts) > 1:
                return address_parts[-1]
        return "Configured Property"

    @classmethod

    def from_env(cls) -> "HouseholdProfile":
        """Factory method to load HouseholdProfile from environment variables."""
        raw_address = (
            os.getenv("HOUSEHOLD_ADDRESS")
            or os.getenv("USER_ADDRESS")
            or os.getenv("ADDRESS")
            or ""
        )
        suburb = os.getenv("HOUSEHOLD_SUBURB") or os.getenv("USER_SUBURB") or os.getenv("SUBURB")
        state = os.getenv("HOUSEHOLD_STATE") or os.getenv("USER_STATE") or os.getenv("STATE")
        postcode = os.getenv("HOUSEHOLD_POSTCODE") or os.getenv("USER_POSTCODE") or os.getenv("POSTCODE")

        elec_usage = (
            os.getenv("HOUSEHOLD_ELECTRICITY_USAGE")
            or os.getenv("USER_ELECTRICITY_USAGE")
            or os.getenv("ELECTRICITY_USAGE")
            or "Medium"
        )
        gas_usage = (
            os.getenv("HOUSEHOLD_GAS_USAGE")
            or os.getenv("USER_GAS_USAGE")
            or os.getenv("GAS_USAGE")
            or "Medium"
        )

        raw_solar = (
            os.getenv("HOUSEHOLD_HAS_SOLAR")
            or os.getenv("HOUSEHOLD_SOLAR")
            or os.getenv("USER_HAS_SOLAR")
            or os.getenv("SOLAR")
            or "true"
        ).strip().lower()
        has_solar = raw_solar in ("true", "1", "yes", "y")

        return cls(
            address=raw_address,
            suburb=suburb,
            state=state,
            postcode=postcode,
            electricity_usage=elec_usage,
            gas_usage=gas_usage,
            has_solar=has_solar,
        )

    def to_prompt_dict(self) -> dict:
        """Returns dictionary suitable for string formatting in prompts."""
        return {
            "address": self.address,
            "suburb": self.suburb or "",
            "state": self.state or "",
            "postcode": self.postcode or "",
            "electricity_usage": self.electricity_usage,
            "gas_usage": self.gas_usage,
            "has_solar": "Yes" if self.has_solar else "No",
            "solar": "Yes" if self.has_solar else "No",
        }

    def format_prompt(self, template: str, **extra_kwargs) -> str:
        """Interpolates household attributes into a prompt template string."""
        context = self.to_prompt_dict()
        context.update(extra_kwargs)
        try:
            return template.format(**context)
        except KeyError:
            # Fallback if unescaped braces exist or missing keys
            formatted = template
            for k, v in context.items():
                formatted = formatted.replace(f"{{{k}}}", str(v))
            return formatted


# Convenience Aliases
PropertyProfile = HouseholdProfile
UserProfile = HouseholdProfile
