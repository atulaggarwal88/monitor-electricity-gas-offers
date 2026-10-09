"""
GloBird Gas Bill Extractor
"""

import re
from typing import Dict, Any
from src.extractors.base_bill import UtilityBill


class GloBirdGasBill(UtilityBill):
    """Parser for GloBird gas account section in a GloBird bill statement."""

    provider = "GloBird"
    utility = "Gas"

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

        gas_section = re.search(
            r"YOUR GAS ACCOUNT.*?(?=YOUR GLOBIRD ENERGY ACCOUNT - IMPORTANT|YOUR GLOBIRD ENERGY ACCOUNT - DETAILED)",
            self.full_text,
            re.DOTALL,
        )
        if gas_section:
            gas_text = gas_section.group(0)

            m = re.search(
                r"Billing Period:\s*(\d{1,2}-\w{3}-\d{4})\s+to\s+(\d{1,2}-\w{3}-\d{4})\s+\((\d+)\s+days\)\s*,?\s*Total Usage:\s*([\d,.]+)\s*MJ",
                gas_text,
            )
            if m:
                record["Period Start"] = m.group(1)
                record["Period End"] = m.group(2)
                record["Days"] = int(m.group(3))
                record["Total Usage"] = m.group(4)
                record["Usage Unit"] = "MJ"

            m = re.search(
                r"Gas Daily Charge\s+\d{1,2}-\w{3}\s+-\s+\d{1,2}-\w{3}\s+(\d+)\s+Days\s+x\s+\$([\d.]+)\s+\$([\d.]+)",
                gas_text,
            )
            if m:
                record["Daily Supply Rate ($/day)"] = m.group(2)
                record["Daily Supply Charge ($)"] = m.group(3)

            usage_matches = re.findall(
                r"Gas Usage\s+\w+\s+-\s+Step\s+\d+.*?([\d,.]+)\s+MJ\s+x\s+\$([\d.]+)\s+\$([\d.]+)",
                gas_text,
            )
            total_gas_usage_charge = sum(float(um[2]) for um in usage_matches)
            if usage_matches:
                record["Usage Rate ($/unit)"] = usage_matches[0][1]
                record["Usage Charge ($)"] = f"{total_gas_usage_charge:.2f}"

            m_sub = re.search(r"SUBTOTAL\s+\(including\s+\$([\d.]+)\s+GST\)\s+\$([\d.]+)", gas_text)
            if m_sub:
                record["Subtotal ($)"] = m_sub.group(2)
                record["GST ($)"] = m_sub.group(1)

            m_disc = re.search(r"Total Discount\s+\$([\d.]+)", gas_text)
            if m_disc:
                record["Discount ($)"] = m_disc.group(1)

            m_total = re.search(r"TOTAL\s+\(including\s+\$([\d.]+)\s+GST\)\s+\$([\d.]+)", gas_text)
            if m_total:
                record["Total ($)"] = m_total.group(2)

        return record


# Alias for requested spelling
GlobirdGasBill = GloBirdGasBill
