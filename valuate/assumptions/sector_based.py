"""
assumptions/sector_based.py
===========================
階段一假設引擎: 用產業分類對照表決定三情境 P/E。

流程:
  1. 從 company 取 sector / industry
  2. 查 sector_map 取得對應 P/E 範圍
  3. 回傳 ScenarioAssumption

完全免費,不需任何 API。
"""

from __future__ import annotations
from .base import AssumptionEngine, ScenarioAssumption
from ..sector_map import get_pe_range


class SectorBasedAssumptions(AssumptionEngine):
    """用產業分類對照表產生假設"""

    def generate(self, company) -> ScenarioAssumption:
        pe_range, match_label = get_pe_range(company.sector, company.industry)

        rationale = (
            f"Per sector-classification table ({match_label}). "
            f"{pe_range.note}"
        )

        return ScenarioAssumption(
            bear_pe=pe_range.bear,
            base_pe=pe_range.base,
            bull_pe=pe_range.bull,
            rationale=rationale,
            source=f"sector_table [{match_label}]",
        )
