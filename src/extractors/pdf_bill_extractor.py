"""
Extract & Consolidate Utility Bills

Parses PDF bill statements (GloBird, EnergyAustralia) using object-oriented
bill classes (UtilityBill parent class and provider/utility specific child classes)
and consolidates billing details into CSV.
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Union
from pathlib import Path
import pandas as pd
from src.config import LANDING_DIR, CONSOLIDATED_CSV_PATH

from src.extractors.base_bill import UtilityBill
from src.extractors.energy_australia_electricity_bill import (
    EnergyAustraliaElectricityBill,
    EnergyAustraliaElectrcityBill,
)
from src.extractors.energy_australia_gas_bill import EnergyAustraliaGasBill
from src.extractors.globird_electricity_bill import (
    GloBirdElectricityBill,
    GlobirdElectrcityBill,
)
from src.extractors.globird_gas_bill import (
    GloBirdGasBill,
    GlobirdGasBill,
)


# Factory dispatchers
def parse_energy_australia_nor(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse an EnergyAustralia electricity (NOR) bill."""
    return [EnergyAustraliaElectricityBill(str(filepath)).parse()]


def parse_energy_australia_gas(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse an EnergyAustralia gas bill."""
    return [EnergyAustraliaGasBill(str(filepath)).parse()]


def parse_globird_bill(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse a GloBird combined electricity & gas bill."""
    return [
        GloBirdElectricityBill(str(filepath)).parse(),
        GloBirdGasBill(str(filepath)).parse(),
    ]


def parse_bill(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """Polymorphic factory function to parse any bill file into record dicts."""
    filepath_str = str(filepath)
    fname = os.path.basename(filepath_str)
    if "energyaustralia" in fname or "energy_australia" in filepath_str or "-NOR" in fname or "-GAS" in fname:
        if "elec" in fname or "-NOR" in fname:
            return parse_energy_australia_nor(filepath_str)
        elif "gas" in fname or "-GAS" in fname:
            return parse_energy_australia_gas(filepath_str)
    elif not fname.startswith("MR"):
        return parse_globird_bill(filepath_str)
    return []


def sort_key(record: Dict[str, Any]) -> datetime:
    """Sort by period start date."""
    date_str = record.get("Period Start", "")
    for fmt in ("%d-%b-%Y", "%d%b%Y", "%d %b %Y"):
        try:
            return datetime.strptime(date_str.replace(" ", ""), "%d%b%Y")
        except ValueError:
            continue
    try:
        return datetime.strptime(date_str, "%d-%b-%Y")
    except ValueError:
        return datetime.min


def extract_and_consolidate_bills(
    landing_directory: str = str(LANDING_DIR),
    output_path: str = str(CONSOLIDATED_CSV_PATH)
) -> pd.DataFrame:
    """Finds all bill PDFs in landing_dir, extracts metrics, and exports consolidated CSV."""
    pdf_files = []
    landing_abs = os.path.abspath(landing_directory)

    if os.path.exists(landing_abs):
        for root, _, files in os.walk(landing_abs):
            for f in sorted(files):
                if f.endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))
    else:
        for f in sorted(os.listdir(".")):
            if f.endswith(".pdf"):
                pdf_files.append(f)

    all_records = []
    for filepath in pdf_files:
        try:
            records = parse_bill(filepath)
            all_records.extend(records)
            if records:
                print(f"  ✓ Parsed: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"  ✗ ERROR parsing {os.path.basename(filepath)}: {e}")

    all_records.sort(key=lambda r: (r.get("Utility", ""), sort_key(r)))
    print(f"Total parsed records: {len(all_records)}")

    columns = [
        "Provider",
        "Utility",
        "Plan",
        "Issue Date",
        "Due Date",
        "Period Start",
        "Period End",
        "Days",
        "Total Usage",
        "Usage Unit",
        "Avg Daily Usage (kWh/day)",
        "Avg Daily Usage (MJ/day)",
        "Usage Rate ($/unit)",
        "Usage Charge ($)",
        "Daily Supply Rate ($/day)",
        "Daily Supply Charge ($)",
        "Subtotal ($)",
        "GST ($)",
        "Discount (%)",
        "Discount ($)",
        "Govt Bill Relief ($)",
        "Total ($)",
        "Combined Bill Total (if paid on time)",
        "File",
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df = pd.DataFrame(all_records)
    df = df.reindex(columns=columns)
    df.to_csv(output_path, index=False)

    print(f"✅ Wrote {len(df)} records to: {output_path}")
    return df
