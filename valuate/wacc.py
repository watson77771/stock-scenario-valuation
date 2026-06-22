"""
wacc.py
=======
WACC (加權平均資金成本 | Weighted Average Cost of Capital | 加重平均資本コスト)
計算 + 護欄。

    WACC = (E/V)·Re + (D/V)·Rd·(1−稅率)
      Re (股權成本) = Rf + 調整後β × ERP            (CAPM)
      Rd (債務成本) = 利息費用 / 總負債 (或 Rf + 利差後備)

所有不可得的輸入都有後備值,確保永遠能算出一個 WACC,但會把每個
「動用後備 / 夾擠」的動作記錄到 notes,讓使用者知道哪裡不可靠。
"""

from __future__ import annotations
from dataclasses import dataclass, field

from . import dcf_params as P


@dataclass
class WACCResult:
    """WACC 計算結果 + 拆解 (供報告透明呈現)"""
    wacc: float
    rf: float
    beta_raw: float | None
    beta_adj: float
    erp: float
    cost_of_equity: float
    cost_of_debt: float
    tax_rate: float
    equity_weight: float
    debt_weight: float
    notes: list[str] = field(default_factory=list)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_wacc(company, rf: float) -> WACCResult:
    """
    計算單一公司的 WACC。

    Args:
        company: CompanyData (需有 beta / market_cap / total_debt /
                 interest_expense / effective_tax_rate 等,缺項自動後備)
        rf:      無風險利率 (由 fetch_risk_free_rate 取得)

    Returns:
        WACCResult
    """
    notes: list[str] = []

    # --- β: Blume 調整 (向 1 均值回歸) + 夾擠 ---
    beta_raw = company.beta
    if beta_raw is None:
        beta_adj = 1.0
        notes.append("無 beta 資料,假設 β=1.0")
    else:
        blume = 0.67 * beta_raw + 0.33 * 1.0
        beta_adj = _clamp(blume, *P.BETA_CLAMP)
        if abs(beta_adj - blume) > 1e-9:
            notes.append(f"β 經夾擠 (Blume {blume:.2f} → {beta_adj:.2f})")

    # --- 股權成本 Re (CAPM) ---
    erp = P.EQUITY_RISK_PREMIUM
    cost_of_equity = rf + beta_adj * erp

    # --- 有效稅率 ---
    tax = company.effective_tax_rate
    if tax is None:
        tax = P.TAX_FALLBACK
        notes.append(f"無法計算有效稅率,用法定 {tax:.0%}")
    else:
        clamped = _clamp(tax, *P.TAX_CLAMP)
        if abs(clamped - tax) > 1e-9:
            notes.append(f"有效稅率經夾擠 ({tax:.0%} → {clamped:.0%})")
        tax = clamped

    # --- 債務成本 Rd ---
    total_debt = company.total_debt or 0.0
    if total_debt > 0 and company.interest_expense:
        rd = abs(company.interest_expense) / total_debt
        clamped = _clamp(rd, *P.COST_OF_DEBT_CLAMP)
        if abs(clamped - rd) > 1e-9:
            notes.append(f"債務成本經夾擠 ({rd:.1%} → {clamped:.1%})")
        rd = clamped
    else:
        rd = rf + P.COST_OF_DEBT_FALLBACK_SPREAD
        notes.append(f"無利息/負債資料,債務成本用 Rf+{P.COST_OF_DEBT_FALLBACK_SPREAD:.1%}")

    # --- 資本結構權重 (用市值,非帳面值) ---
    E = company.market_cap or 0.0
    D = total_debt
    V = E + D
    if V <= 0:
        equity_weight, debt_weight = 1.0, 0.0
        notes.append("無市值/負債資料,假設 100% 股權結構")
    else:
        equity_weight = E / V
        debt_weight = D / V

    wacc = equity_weight * cost_of_equity + debt_weight * rd * (1 - tax)

    # --- 護欄: 合理區間健檢 ---
    lo, hi = P.WACC_SANITY
    if not (lo <= wacc <= hi):
        notes.append(
            f"WACC {wacc:.1%} 落在合理區間 {lo:.0%}–{hi:.0%} 外,參數可能失真,請檢視"
        )

    return WACCResult(
        wacc=round(wacc, 4),
        rf=rf,
        beta_raw=beta_raw,
        beta_adj=round(beta_adj, 2),
        erp=erp,
        cost_of_equity=round(cost_of_equity, 4),
        cost_of_debt=round(rd, 4),
        tax_rate=round(tax, 4),
        equity_weight=round(equity_weight, 3),
        debt_weight=round(debt_weight, 3),
        notes=notes,
    )
