"""
peg.py
======
PEG (本益成長比) 估值引擎 —— 第三種估值法,補 DCF 與 P/E 法看不到的「成長溢價」。

產出三樣東西:
  1. trailing PEG = (現價/歷史EPS) ÷ 歷史 EPS 成長率   (用 EDGAR 歷史 EPS,看實績)
  2. forward  PEG = (現價/預估EPS) ÷ 未來 EPS 成長率   (用 FMP 分析師預估,看市場在賭的)
  3. 成長校正目標價 (Lynch fair value): target = (成長率% × 目標PEG) × EPS
     三情境只變「目標 PEG」(market 願意為每單位成長付幾倍),反映情緒保守/中性/樂觀。

關鍵紀律: PEG 只對「正成長、獲利穩定的成長型公司」有意義。對零/負成長、景氣循環、
金融、虧損股會自動 gating —— 標警示、不產(或標不可靠)目標價,引導改用 DCF。
"""

from __future__ import annotations
from dataclasses import dataclass, field

from . import peg_params as PP
from .datasources import robust_eps_cagr


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


@dataclass
class ScenarioPEG:
    target_peg: float        # 該情境採用的目標 PEG
    fair_pe: float           # 成長率% × 目標PEG = 合理本益比
    target: float            # 每股目標價
    ret: float               # 相對現價報酬率


@dataclass
class PEGResult:
    ticker: str
    name: str
    current_price: float
    sector: str | None
    industry: str | None

    trailing_eps: float | None
    forward_eps_used: float | None

    trailing_pe: float | None
    trailing_growth: float | None
    trailing_peg: float | None

    forward_pe: float | None
    forward_growth: float | None
    forward_peg: float | None

    growth_used: float | None        # 用於成長校正目標價的成長率 (已 clamp)
    growth_source: str               # 成長率來源說明
    eps_used_for_target: float | None

    bear: ScenarioPEG | None
    base: ScenarioPEG | None
    bull: ScenarioPEG | None

    applicable: bool                 # PEG 對這檔是否有意義 (gating 結論)
    rationale: str = ""
    source: str = "peg"
    analyst_target_mean: float | None = None
    warnings: list = field(default_factory=list)


def _peg_ratio(pe: float | None, growth: float | None) -> float | None:
    """PEG = PE ÷ 成長率(%)。成長 ≤ 0 或 PE ≤ 0 → 無意義回 None。"""
    if pe is None or pe <= 0 or growth is None or growth <= 0:
        return None
    return round(pe / (growth * 100), 2)


class PEGEngine:
    """成長校正估值引擎。"""

    def value(self, company, eps_history: list | None = None,
              fwd_estimates: dict | None = None) -> PEGResult:
        price = company.current_price
        trail_eps = company.trailing_eps
        warnings: list[str] = []

        # --- trailing 腿: EDGAR 歷史 EPS ---
        trailing_growth = robust_eps_cagr(eps_history) if eps_history else None
        trailing_pe = (round(price / trail_eps, 2)
                       if (price and trail_eps and trail_eps > 0) else None)
        trailing_peg = _peg_ratio(trailing_pe, trailing_growth)

        # --- forward 腿: FMP 預估 EPS ---
        forward_growth = fwd_estimates.get("growth") if fwd_estimates else None
        fwd_eps = None
        if fwd_estimates and fwd_estimates.get("forward_eps"):
            fwd_eps = fwd_estimates["forward_eps"]
        elif company.forward_eps:
            fwd_eps = company.forward_eps          # 退回 yfinance forward EPS
        forward_pe = (round(price / fwd_eps, 2)
                      if (price and fwd_eps and fwd_eps > 0) else None)
        forward_peg = _peg_ratio(forward_pe, forward_growth)

        # --- 決定成長校正用的成長率與 EPS ---
        # 優先未來成長 (PEG 本意),退回歷史成長;EPS 優先 forward,退回 trailing
        growth_raw, growth_source = (
            (forward_growth, "FMP forward EPS growth") if forward_growth is not None
            else (trailing_growth, "EDGAR historical EPS growth") if trailing_growth is not None
            else (None, "no growth data"))
        eps_for_target = fwd_eps if (fwd_eps and fwd_eps > 0) else (
            trail_eps if (trail_eps and trail_eps > 0) else None)

        # ============ Gating: PEG 是否適用 ============
        applicable = True
        if eps_for_target is None:
            applicable = False
            warnings.append("EPS <= 0 (loss-making); P/E is meaningless, PEG / growth-adjustment N/A, use DCF")
        if growth_raw is None:
            applicable = False
            warnings.append("Insufficient 3-5yr EPS growth data; cannot compute PEG (EDGAR/FMP both missing)")
        elif growth_raw < PP.PEG_MIN_GROWTH:
            applicable = False
            warnings.append(
                f"Low growth ({growth_raw:+.1%} < {PP.PEG_MIN_GROWTH:.0%}); PEG denominator too small "
                f"and distorted. Use DCF / dividend-discount for such stocks; targets flagged unreliable")
        elif growth_raw > PP.PEG_MAX_GROWTH:
            warnings.append(
                f"Very high growth ({growth_raw:+.1%} > {PP.PEG_MAX_GROWTH:.0%}); unsustainable, "
                f"PEG is optimistic. Growth clamped to cap for the calc, use with caution")

        # Sector applicability note
        if company.sector in PP.PEG_WEAK_SECTORS or company.industry in PP.PEG_WEAK_INDUSTRIES:
            warnings.append(
                f"{company.sector or ''}/{company.industry or ''}: cyclical/financial/low-growth sector; "
                f"EPS growth not representative, PEG of weak reference value")

        # --- 成長校正目標價 (即使 gating 不佳仍計算,但會帶警示) ---
        bear = base = bull = None
        growth_used = None
        if growth_raw is not None and eps_for_target is not None:
            growth_used = _clamp(growth_raw, *PP.GROWTH_CLAMP)

            def build(scn: str) -> ScenarioPEG:
                tpeg = PP.TARGET_PEG[scn]
                fair_pe = growth_used * 100 * tpeg
                target = round(fair_pe * eps_for_target, 2)
                ret = round(target / price - 1, 4) if price else 0.0
                return ScenarioPEG(target_peg=tpeg, fair_pe=round(fair_pe, 1),
                                   target=target, ret=ret)

            bear, base, bull = build("bear"), build("base"), build("bull")

        if base is not None:
            rationale = (
                f"Growth-adjusted (PEG/Lynch). Growth {growth_used:+.1%} ({growth_source}), "
                f"EPS=${eps_for_target:.2f}. Scenario target PEG="
                f"{PP.TARGET_PEG['bear']}/{PP.TARGET_PEG['base']}/{PP.TARGET_PEG['bull']} "
                f"(fair P/E {bear.fair_pe:.0f}/{base.fair_pe:.0f}/{bull.fair_pe:.0f}x). "
                f"trailing PEG={trailing_peg} / forward PEG={forward_peg}.")
        else:
            rationale = f"PEG not applicable: {growth_source}. trailing PEG={trailing_peg}"

        # 與分析師均價對照
        if company.analyst_target_mean and base is not None and base.target:
            diff = base.target / company.analyst_target_mean - 1
            if abs(diff) > 0.35:
                warnings.append(
                    f"Growth-adjusted Base (${base.target}) vs analyst avg "
                    f"(${company.analyst_target_mean:.0f}) differ {diff:+.0%}; growth assumption may need review")

        return PEGResult(
            ticker=company.ticker, name=company.name, current_price=price,
            sector=company.sector, industry=company.industry,
            trailing_eps=trail_eps, forward_eps_used=fwd_eps,
            trailing_pe=trailing_pe, trailing_growth=trailing_growth, trailing_peg=trailing_peg,
            forward_pe=forward_pe, forward_growth=forward_growth, forward_peg=forward_peg,
            growth_used=growth_used, growth_source=growth_source,
            eps_used_for_target=eps_for_target,
            bear=bear, base=base, bull=bull,
            applicable=applicable, rationale=rationale,
            analyst_target_mean=company.analyst_target_mean, warnings=warnings,
        )
