"""
engine.py
=========
估值引擎: 把公司資料 + 假設 → 三情境目標價。

目前實作 P/E 法 (最通用)。
未來可擴展 SOTP / FCF 法 (預留介面)。
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ValuationResult:
    """估值結果"""
    ticker: str
    name: str
    current_price: float
    eps_used: float
    eps_type: str            # "forward" 或 "trailing"

    bear_pe: float
    base_pe: float
    bull_pe: float

    bear_target: float = 0.0
    base_target: float = 0.0
    bull_target: float = 0.0

    bear_return: float = 0.0   # 相對現價報酬率
    base_return: float = 0.0
    bull_return: float = 0.0

    rationale: str = ""
    source: str = ""

    # 參考資料
    analyst_target_mean: float | None = None
    sector: str | None = None
    industry: str | None = None

    warnings: list[str] = field(default_factory=list)


class ValuationEngine:
    """P/E 法估值引擎"""

    def __init__(self, assumption_engine):
        """
        Args:
            assumption_engine: AssumptionEngine 實例
                               (SectorBased 或 LLMBased)
        """
        self.assumption_engine = assumption_engine

    def value(self, company) -> ValuationResult:
        """
        對單一公司執行估值。

        Args:
            company: CompanyData (來自 fetcher)

        Returns:
            ValuationResult
        """
        if not company.is_valid:
            raise ValueError(
                f"{company.ticker} 資料不足無法估值 "
                f"(現價={company.current_price}, "
                f"forward_eps={company.forward_eps}, "
                f"trailing_eps={company.trailing_eps})"
            )

        # 1. 取 EPS
        eps = company.best_eps
        eps_type = "forward" if company.forward_eps else "trailing"

        # 2. 取假設 (三情境 P/E)
        assumption = self.assumption_engine.generate(company)

        # 3. 計算目標價 = EPS × P/E
        result = ValuationResult(
            ticker=company.ticker,
            name=company.name,
            current_price=company.current_price,
            eps_used=eps,
            eps_type=eps_type,
            bear_pe=assumption.bear_pe,
            base_pe=assumption.base_pe,
            bull_pe=assumption.bull_pe,
            rationale=assumption.rationale,
            source=assumption.source,
            analyst_target_mean=company.analyst_target_mean,
            sector=company.sector,
            industry=company.industry,
        )

        result.bear_target = round(eps * assumption.bear_pe, 2)
        result.base_target = round(eps * assumption.base_pe, 2)
        result.bull_target = round(eps * assumption.bull_pe, 2)

        # 4. 報酬率
        p = company.current_price
        result.bear_return = round(result.bear_target / p - 1, 4)
        result.base_return = round(result.base_target / p - 1, 4)
        result.bull_return = round(result.bull_target / p - 1, 4)

        # 5. 警示
        if eps_type == "trailing":
            result.warnings.append(
                "使用 trailing EPS (無 forward 預估),估值偏保守"
            )
        if eps <= 0:
            result.warnings.append(
                "EPS <= 0 (公司虧損中),P/E 法不適用,結果僅供參考"
            )
        if company.analyst_target_mean:
            # 比對自己的 Base vs 分析師
            diff = result.base_target / company.analyst_target_mean - 1
            if abs(diff) > 0.30:
                result.warnings.append(
                    f"Base 目標 (${result.base_target}) 與分析師均價 "
                    f"(${company.analyst_target_mean:.0f}) 差異 {diff:+.0%},"
                    f"產業倍數可能需調整"
                )

        return result
