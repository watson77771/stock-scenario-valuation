"""
assumptions/base.py
===================
估值假設引擎的抽象介面。

設計目的:
  把「三情境 P/E 倍數怎麼產生」這件事抽象化,讓不同策略可以替換:
    - SectorBasedAssumptions (階段一): 用產業分類對照表
    - LLMBasedAssumptions   (階段三): 呼叫 Claude API 動態生成

主程式只依賴這個介面,不關心底層用哪種策略。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ScenarioAssumption:
    """三情境的估值假設輸出"""
    bear_pe: float
    base_pe: float
    bull_pe: float
    rationale: str = ""        # 為何給這些倍數
    source: str = ""           # 來源 (sector_table / llm / manual)

    def as_dict(self) -> dict:
        return {
            "bear_pe": self.bear_pe,
            "base_pe": self.base_pe,
            "bull_pe": self.bull_pe,
            "rationale": self.rationale,
            "source": self.source,
        }


class AssumptionEngine(ABC):
    """假設引擎抽象基類"""

    @abstractmethod
    def generate(self, company) -> ScenarioAssumption:
        """
        根據公司資料產生三情境 P/E 假設。

        Args:
            company: CompanyData 物件 (來自 fetcher)

        Returns:
            ScenarioAssumption
        """
        ...
