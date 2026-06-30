"""
sector_map.py
=============
Sector classification -> three-scenario P/E multiple table.

This is the core of the "stage 1" assumption. yfinance returns each company's
sector / industry; this module maps them to sensible Bear / Base / Bull P/E ranges.

Design:
  - Reasonable multiples differ greatly across sectors (semis vs energy vs banks)
  - Within a sector, Bull/Base/Bear reflect optimistic/neutral/pessimistic sentiment
  - These multiples are judgments; users can override in config

Source: the author's (Watson) valuation experience across sectors + historical P/E ranges.
Disclaimer: these are rules of thumb, not investment advice. Adjust as markets change.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PERange:
    """Three-scenario P/E range for a single sector."""
    bear: float
    base: float
    bull: float
    note: str = ""

    def as_dict(self) -> dict:
        return {"bear": self.bear, "base": self.base, "bull": self.bull, "note": self.note}


# ============================================================
# Sector P/E table
# ============================================================
# Keys map to yfinance sector (coarse) or industry (fine).
# Fine-grained industry takes priority over coarse sector.
# ============================================================

# --- Industry-level (fine, matched first) ---
INDUSTRY_PE_RANGES: dict[str, PERange] = {
    # Semiconductors (high growth + cyclical + AI theme)
    "Semiconductors": PERange(18, 28, 40, "AI tailwind / cyclical / leaders command a premium"),
    "Semiconductor Equipment & Materials": PERange(16, 24, 34, "Equipment makers / track the capex cycle"),

    # Software (ARR model / high multiple tolerance)
    "Software - Infrastructure": PERange(22, 34, 48, "Infrastructure software / high stickiness"),
    "Software - Application": PERange(20, 32, 45, "Application software / SaaS ARR premium"),

    # Internet / media
    "Internet Content & Information": PERange(18, 26, 36, "Ads + platform / exposed to AI disruption & regulation"),
    "Internet Retail": PERange(20, 32, 50, "E-commerce / growth-driven valuation"),

    # Hardware / equipment
    "Consumer Electronics": PERange(18, 26, 34, "Brand premium / Apple-like"),
    "Communication Equipment": PERange(14, 20, 28, "Networking gear / more mature"),
    "Computer Hardware": PERange(12, 18, 26, "Hardware / lower margins"),

    # Energy (cyclical / low multiple)
    "Oil & Gas Refining & Marketing": PERange(8, 12, 16, "Refining / crack-spread cycle"),
    "Oil & Gas Integrated": PERange(9, 13, 18, "Integrated oil / driven by oil price"),
    "Oil & Gas E&P": PERange(7, 11, 15, "Upstream E&P / highly cyclical"),
    "Uranium": PERange(15, 30, 60, "Nuclear theme / pre-revenue story stocks, very volatile"),
    "Solar": PERange(10, 18, 30, "Policy-driven / subsidy-sensitive"),

    # Financials
    "Banks - Diversified": PERange(8, 11, 14, "Large banks / rate- and regulation-sensitive"),
    "Banks - Regional": PERange(7, 10, 13, "Regional banks / credit-risk sensitive"),
    "Credit Services": PERange(12, 18, 26, "Payments / credit cards / higher growth"),
    "Capital Markets": PERange(10, 15, 22, "Investment banks / asset mgmt / market-linked"),
    "Insurance - Diversified": PERange(8, 12, 16, "Insurance / steady low growth"),

    # Industrials / defense
    "Aerospace & Defense": PERange(15, 22, 30, "Defense / high order visibility"),
    "Specialty Industrial Machinery": PERange(14, 20, 28, "Industrial machinery / tracks the cycle"),

    # Mining / materials
    "Other Industrial Metals & Mining": PERange(8, 15, 28, "Metals mining / commodity-price driven / high volatility"),
    "Lithium": PERange(10, 20, 40, "Lithium / EV demand + pre-revenue risk"),

    # Healthcare
    "Drug Manufacturers - General": PERange(12, 18, 26, "Big pharma / patent-cliff risk"),
    "Biotechnology": PERange(15, 30, 60, "Biotech / binary trial outcomes / high volatility"),
    "Medical Devices": PERange(18, 26, 36, "Medical devices / steady growth"),

    # Consumer
    "Auto Manufacturers": PERange(8, 18, 35, "Automakers / traditionally low multiple but EV/AI themes diverge widely"),
    "Restaurants": PERange(18, 25, 35, "Restaurants / brand and store expansion"),
    "Beverages - Non-Alcoholic": PERange(18, 24, 30, "Beverages / defensive consumer"),

    # Fintech / exchanges
    "Financial Data & Stock Exchanges": PERange(15, 25, 38, "Financial data / exchanges"),
}

# --- Sector-level (coarse, fallback when no industry match) ---
SECTOR_PE_RANGES: dict[str, PERange] = {
    "Technology": PERange(18, 28, 42, "Technology / growth-driven"),
    "Communication Services": PERange(15, 24, 36, "Communication services / ads + media"),
    "Energy": PERange(8, 12, 17, "Energy / cyclical"),
    "Financial Services": PERange(9, 13, 19, "Financials / rate-sensitive"),
    "Healthcare": PERange(14, 22, 32, "Healthcare / defensive + innovation mix"),
    "Consumer Cyclical": PERange(12, 20, 32, "Consumer cyclical"),
    "Consumer Defensive": PERange(16, 22, 28, "Consumer defensive / stable"),
    "Industrials": PERange(14, 20, 28, "Industrials / tracks the cycle"),
    "Basic Materials": PERange(9, 15, 26, "Basic materials / commodity-price driven"),
    "Real Estate": PERange(12, 18, 26, "Real estate / REITs / rate-sensitive"),
    "Utilities": PERange(14, 18, 22, "Utilities / defensive low growth"),
}

# --- Final fallback (no sector at all) ---
DEFAULT_PE_RANGE = PERange(12, 18, 26, "Generic default / no sector info")


def get_pe_range(sector: str | None, industry: str | None) -> tuple[PERange, str]:
    """
    Return a sensible P/E range from yfinance sector / industry.

    Priority: industry (fine) > sector (coarse) > default

    Returns:
        (PERange, match-level label)
    """
    if industry and industry in INDUSTRY_PE_RANGES:
        return INDUSTRY_PE_RANGES[industry], f"industry: {industry}"

    if sector and sector in SECTOR_PE_RANGES:
        return SECTOR_PE_RANGES[sector], f"sector: {sector}"

    label = f"default (sector={sector}, industry={industry})"
    return DEFAULT_PE_RANGE, label


def list_supported() -> dict:
    """List all supported sectors (for CLI --list-sectors)."""
    return {
        "industries": sorted(INDUSTRY_PE_RANGES.keys()),
        "sectors": sorted(SECTOR_PE_RANGES.keys()),
    }
