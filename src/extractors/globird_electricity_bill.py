"""
GloBird Electricity Bill Extractor
"""

import re
from typing import Dict, Any
from src.extractors.base_bill import UtilityBill


class GloBirdElectricityBill(UtilityBill):
    """Parser for GloBird electricity account section in a GloBird bill statement."""

    provider = "GloBird"
    utility = "Electricity"

    def parse(self) -> Dict[str, Any]:
        record = {
            "Provider": self.provider,
            "Utility": self.utility,
            "File": self.filename,
        }

        m = re.search(r"Issue Date\s+(\d{1,2}-\w{3}-\d{4})", self.full_text)
        if m:
            record["Issue Date"] = m.group(1)

        m = re.search(r"Due Date(?:\s+\(Direct Debit Date\))?\s+(\d{1,2}-\w{3}-\d{4})", self.full_text)
        if m:
            record["Due Date"] = m.group(1)

        m = re.search(
            r"YOUR ELECTRICITY ACCOUNT.*?Billing Period:\s*(\d{1,2}-\w{3}-\d{4})\s+to\s+(\d{1,2}-\w{3}-\d{4})\s+\((\d+)\s+days\)\s*,?\s*Total Usage:\s*([\d,.]+)\s*kWh",
            self.full_text,
            re.DOTALL,
        )
        if m:
            record["Period Start"] = m.group(1)
            record["Period End"] = m.group(2)
            record["Days"] = int(m.group(3))
            record["Total Usage"] = m.group(4)
            record["Usage Unit"] = "kWh"

        m = re.search(
            r"Daily Charge\s+\d{1,2}-\w{3}\s+-\s+\d{1,2}-\w{3}\s+(\d+)\s+Days\s+x\s+\$([\d.]+)\s+\$([\d.]+)",
            self.full_text,
        )
        if m:
            record["Daily Supply Rate ($/day)"] = m.group(2)
            record["Daily Supply Charge ($)"] = m.group(3)

        elec_section = re.search(
            r"YOUR ELECTRICITY ACCOUNT.*?(?=YOUR GAS ACCOUNT|YOUR GLOBIRD ENERGY ACCOUNT - IMPORTANT)",
            self.full_text,
            re.DOTALL,
        )
        if elec_section:
            elec_text = elec_section.group(0)

            usage_matches = re.findall(
                r"(Anytime Usage[^\n]*?)\s+([\d,.]+)\s+kWh\s+x\s+\$([\d.]+)\s+\$([\d.]+)",
                elec_text,
            )
            total_usage_charge = sum(float(um[3]) for um in usage_matches)
            if usage_matches:
                record["Usage Rate ($/unit)"] = usage_matches[0][2]
                record["Usage Charge ($)"] = f"{total_usage_charge:.2f}"

            m_sub = re.search(r"SUBTOTAL\s+\(including\s+\$([\d.]+)\s+GST\)\s+\$([\d.]+)", elec_text)
            if m_sub:
                record["Subtotal ($)"] = m_sub.group(2)
                record["GST ($)"] = m_sub.group(1)

            m_disc = re.search(r"Total Discount\s+\$([\d.]+)", elec_text)
            if m_disc:
                record["Discount ($)"] = m_disc.group(1)

            m_total = re.search(r"TOTAL\s+\(including\s+\$([\d.]+)\s+GST\)\s+\$([\d.]+)", elec_text)
            if m_total:
                record["Total ($)"] = m_total.group(2)

        m_combined = re.search(r"TOTAL IF PAID ON TIME\s*=\s*\$([\d,.]+)", self.full_text)
        if m_combined:
            record["Combined Bill Total (if paid on time)"] = m_combined.group(1)
        else:
            m_combined = re.search(r"if paid by.*?\n\$([\d,.]+)", self.full_text)
            if m_combined:
                record["Combined Bill Total (if paid on time)"] = m_combined.group(1)

        return record


# Alias for requested spelling
GlobirdElectrcityBill = GloBirdElectricityBill
