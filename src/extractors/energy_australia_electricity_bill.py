"""
EnergyAustralia Electricity Bill Extractor
"""

import re
from datetime import datetime
from typing import Dict, Any
from src.extractors.base_bill import UtilityBill


class EnergyAustraliaElectricityBill(UtilityBill):
    """Parser for EnergyAustralia electricity (NOR) bills."""

    provider = "EnergyAustralia"
    utility = "Electricity"

    def parse(self) -> Dict[str, Any]:
        record = {
            "Provider": self.provider,
            "Utility": self.utility,
            "File": self.filename,
        }

        # 1. Total ($)
        m = re.search(r"Total\s*amount\s*due\s*\n?\$?([\d,.]+)", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Total\s*amount\s*due\s*\(incl\.\s*GST\)\s*\$?([\d,.]+)", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Total\s*Current\s*Charges\s*\(incl\.\s*GST.*?\)\s*\$?([\d,.]+)", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Amountdue\s*\n?\$?([\d,.]+)", self.text_ns, re.IGNORECASE)
        if not m:
            m = re.search(r"Totalamount\(incl\.GST\)\$?([\d,.]+)", self.text_ns, re.IGNORECASE)
        if m:
            record["Total ($)"] = m.group(1).replace(",", "")

        # 2. Issue Date
        m = re.search(r"(?:Tax\s*Invoice\s*)?Bill\s*issue\s*date:?\s*(\d{1,2}\s*[A-Za-z]{3}\s*\d{4})", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Issue\s*date:?\s*(\d{1,2}\s*[A-Za-z]{3}\s*\d{4})", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Billissuedate:?(\d{1,2}[A-Za-z]{3}\d{4})", self.text_ns, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            m_dt = re.match(r"(\d{1,2})([A-Za-z]{3})(\d{4})", val.replace(" ", ""))
            if m_dt:
                val = f"{m_dt.group(1)} {m_dt.group(2)} {m_dt.group(3)}"
            record["Issue Date"] = val

        # 3. Due Date
        m = re.search(r"(?:Direct\s*debit\s*)?due\s*date:?\s*(?:Direct\s*Debit\s*)?(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Direct\s*Debit\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Direct\s*debit\s*to\s*your.*?(?:take\s*place\s*on\s*|on\s*)(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", self.full_text, re.IGNORECASE)
            if m:
                dstr = m.group(1).strip()
                try:
                    dt = datetime.strptime(dstr, "%d-%m-%Y")
                    dstr = dt.strftime("%d %b %Y")
                except ValueError:
                    pass
                record["Due Date"] = dstr
        if not m and "Due Date" not in record:
            m = re.search(r"Directdebitduedate(\d{1,2}[A-Za-z]{3}\d{4})", self.text_ns, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                m_dt = re.match(r"(\d{1,2})([A-Za-z]{3})(\d{4})", val)
                if m_dt:
                    val = f"{m_dt.group(1)} {m_dt.group(2)} {m_dt.group(3)}"
                record["Due Date"] = val

        # 4. Period Start & Period End
        period_matches = re.findall(r"(\d{1,2}\s*[A-Za-z]{3}\s*\d{4})\s*to\s*(\d{1,2}\s*[A-Za-z]{3}\s*\d{4})", self.full_text, re.IGNORECASE)
        if not period_matches:
            period_matches = re.findall(r"(\d{1,2}[A-Za-z]{3}\d{4})to(\d{1,2}[A-Za-z]{3}\d{4})", self.text_ns, re.IGNORECASE)

        if period_matches:
            starts = []
            ends = []
            for p_start, p_end in period_matches:
                s_clean = p_start.replace(" ", "")
                e_clean = p_end.replace(" ", "")
                try:
                    dt_s = datetime.strptime(s_clean, "%d%b%Y")
                    dt_e = datetime.strptime(e_clean, "%d%b%Y")
                    starts.append((dt_s, p_start))
                    ends.append((dt_e, p_end))
                except ValueError:
                    pass
            if starts and ends:
                min_start = min(starts, key=lambda x: x[0])
                max_end = max(ends, key=lambda x: x[0])
                record["Period Start"] = min_start[0].strftime("%d %b %Y")
                record["Period End"] = max_end[0].strftime("%d %b %Y")

        # 5. Plan
        m = re.search(r"Your\s*current\s*plan:?\s*([A-Za-z0-9\s()]+?)(?=\n|Includes:|Opening|Carbon|\d{2}/)", self.full_text, re.IGNORECASE)
        if m:
            p = re.sub(r"\s+", " ", m.group(1)).strip()
            if p and not p.lower().startswith("is the") and not p.lower().startswith("summary"):
                record["Plan"] = p

        if "Plan" not in record:
            m = re.search(r"(Flexi\s*Plan\s*\(Home\)|FlexiPlan\(Home\)|Balance\s*Plan\s*\(Home\)|Total\s*Plan\s*Plus\s*12\s*\(Home\))", self.full_text, re.IGNORECASE)
            if m:
                record["Plan"] = re.sub(r"\s+", " ", m.group(1)).strip()

        # 6. Usage lines
        usage_matches = re.findall(
            r"Peak\s*Consumption\s*\(?\s*([\d.]+)\s*kWh/day\)?\^?\s*([\d,.]+)\s*kWh\s+\$?([\d.]+)\s*per\s*kWh\s+\$?([\d.]+)",
            self.full_text,
            re.IGNORECASE,
        )
        if not usage_matches:
            usage_matches = re.findall(
                r"PeakConsumption\(?([\d.]+)\s*kWh/day\)?\^?\s*([\d,.]+)\s*kWh\$?([\d.]+)\s*perkWh\$?([\d.]+)",
                self.text_ns,
                re.IGNORECASE,
            )

        if usage_matches:
            total_kwh = sum(float(um[1].replace(",", "")) for um in usage_matches)
            total_usage_charge = sum(float(um[3]) for um in usage_matches)
            record["Total Usage"] = f"{total_kwh:.3f}"
            record["Usage Unit"] = "kWh"
            record["Usage Rate ($/unit)"] = usage_matches[0][2]
            record["Usage Charge ($)"] = f"{total_usage_charge:.2f}"

        # 7. Supply Charge lines
        supply_matches = re.findall(
            r"Supply\s*Charge\s+(\d+)\s*days\s+\$?([\d.]+)\s*per\s*day\s+\$?([\d.]+)",
            self.full_text,
            re.IGNORECASE,
        )
        if not supply_matches:
            supply_matches = re.findall(
                r"SupplyCharge(\d+)\s*days\$?([\d.]+)\s*perday\$?([\d.]+)",
                self.text_ns,
                re.IGNORECASE,
            )
        if supply_matches:
            total_supply_days = sum(int(sm[0]) for sm in supply_matches)
            total_supply_charge = sum(float(sm[2]) for sm in supply_matches)
            record["Daily Supply Rate ($/day)"] = supply_matches[0][1]
            record["Daily Supply Charge ($)"] = f"{total_supply_charge:.2f}"
            record["Days"] = total_supply_days

        if "Days" not in record and "Period Start" in record and "Period End" in record:
            dt_start = datetime.strptime(record["Period Start"], "%d %b %Y")
            dt_end = datetime.strptime(record["Period End"], "%d %b %Y")
            record["Days"] = (dt_end - dt_start).days + 1

        if record.get("Total Usage") and record.get("Days"):
            avg = float(record["Total Usage"]) / float(record["Days"])
            record["Avg Daily Usage (kWh/day)"] = f"{avg:.5f}"

        # 8. GST & Subtotal
        m = re.search(r"Total\s*current\s*charges\s*\(incl\.\s*GST\s*of\s*\$?([\d.]+)\)\s+\$?([\d.]+)", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Totalcurrentcharges\(incl\.GSTof\$?([\d.]+)\)\$?([\d.]+)", self.text_ns, re.IGNORECASE)
        if m:
            record["GST ($)"] = m.group(1)
            record["Subtotal ($)"] = m.group(2)

        # 9. Discount
        m = re.search(r"Discount\s*-\s*(\d+)%\s+\$?([\d.]+)CR", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"Discount-(\d+)%\$?([\d.]+)CR", self.text_ns, re.IGNORECASE)
        if m:
            record["Discount (%)"] = m.group(1)
            record["Discount ($)"] = m.group(2)

        # 10. Govt Bill Relief
        m = re.search(r"(?:Australian\s*)?Government\s*Energy\s*(?:Bill\s*)?Relief\s+\$?([\d.]+)CR", self.full_text, re.IGNORECASE)
        if not m:
            m = re.search(r"(?:Australian)?GovernmentEnergy(?:Bill)?Relief\$?([\d.]+)CR", self.text_ns, re.IGNORECASE)
        if m:
            record["Govt Bill Relief ($)"] = m.group(1)

        return record


# Alias for requested spelling
EnergyAustraliaElectrcityBill = EnergyAustraliaElectricityBill
