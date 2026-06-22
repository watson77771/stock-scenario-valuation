"""
dcf.py
======
DCF (折現現金流) 估值引擎 — 階段二新增的「第二種估值法」。

與 P/E 法 (engine.py) 並存,互為交叉驗證:
  P/E 法 = 市場願意給幾倍 (靠別人的情緒)
  DCF 法 = 公司一輩子生多少現金折回今天 (靠公司本身)

五步驟:
  1. 取基準自由現金流 (FCF)
  2. 預測未來 N 年 FCF (依成長率 g)
  3. 折現率 WACC (見 wacc.py)
  4. 終值 TV = FCF_N × (1+g_終) / (WACC − g_終)   ← Gordon 永續成長
  5. 折現加總 → 企業價值 EV → 減淨負債 → 每股目標價

三情境只變「FCF 成長率 g」與「終值成長 g_終」,WACC 三情境共用
(對應 dcf_params 設計原則: 只有營運層隨情境變)。
"""

from __future__ import annotations
from dataclasses import dataclass, field

from . import dcf_params as P
from .wacc import compute_wacc, WACCResult


@dataclass
class ScenarioDCF:
    """單一情境的 DCF 結果"""
    growth: float            # FCF 成長率 g
    terminal_growth: float   # 終值成長 g_終
    target: float            # 每股目標價
    ret: float               # 相對現價報酬率
    ev: float                # 企業價值 (Enterprise Value)
    equity_value: float      # 股權價值 = EV − 淨負債
    tv_share: float          # 終值現值佔 EV 比 (健檢用)


@dataclass
class DCFResult:
    """完整 DCF 估值結果"""
    ticker: str
    name: str
    current_price: float
    base_fcf: float
    fcf_source: str
    shares_outstanding: float
    net_debt: float
    wacc: WACCResult
    projection_years: int

    bear: ScenarioDCF
    base: ScenarioDCF
    bull: ScenarioDCF

    sensitivity: list = field(default_factory=list)   # WACC × 終值成長 敏感度表
    rationale: str = ""
    source: str = "dcf"
    sector: str | None = None
    industry: str | None = None
    analyst_target_mean: float | None = None
    warnings: list[str] = field(default_factory=list)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _discount(base_fcf: float, growth: float, terminal_growth: float,
              wacc: float, years: int) -> tuple[float, float]:
    """
    把 FCF 折現成企業價值。

    Returns:
        (ev, tv_share)  EV 與「終值現值佔 EV 比」
    """
    pv_explicit = 0.0
    fcf_t = base_fcf
    for t in range(1, years + 1):
        fcf_t = base_fcf * (1 + growth) ** t
        pv_explicit += fcf_t / (1 + wacc) ** t

    # 終值 (Gordon Growth);fcf_t 此時為第 N 年的 FCF
    tv = fcf_t * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_tv = tv / (1 + wacc) ** years

    ev = pv_explicit + pv_tv
    tv_share = pv_tv / ev if ev else 0.0
    return ev, tv_share


def _derive_growth(company) -> tuple[dict, str]:
    """
    決定三情境 FCF 成長率。
    優先用歷史 FCF CAGR 當 Base 錨,上下展開;否則用產業通用預設。
    """
    hist = company.fcf_cagr
    if hist is not None:
        base_g = _clamp(hist, *P.GROWTH_CLAMP)
        bear_g = _clamp(base_g - P.GROWTH_SPREAD_DOWN, *P.GROWTH_CLAMP)
        bull_g = _clamp(base_g + P.GROWTH_SPREAD_UP, *P.GROWTH_CLAMP)
        return ({"bear": bear_g, "base": base_g, "bull": bull_g},
                f"歷史 FCF CAGR {hist:+.1%} 為 Base 錨")
    return dict(P.DEFAULT_GROWTH), "無足夠歷史 FCF,用通用成長預設"


class DCFEngine:
    """FCF 折現估值引擎"""

    def __init__(self, risk_free_rate: float):
        self.rf = risk_free_rate

    def value(self, company) -> DCFResult:
        if not company.has_dcf_data:
            raise ValueError(
                f"{company.ticker} 缺 DCF 必要資料 "
                f"(FCF={company.free_cashflow}, shares={company.shares_outstanding}, "
                f"price={company.current_price})"
            )

        base_fcf = company.free_cashflow
        wacc_res = compute_wacc(company, self.rf)
        wacc = wacc_res.wacc
        years = P.PROJECTION_YEARS
        shares = company.shares_outstanding
        net_debt = company.net_debt or 0.0
        price = company.current_price

        growth, growth_src = _derive_growth(company)

        warnings = list(wacc_res.notes)
        if base_fcf <= 0:
            warnings.append("基準 FCF ≤ 0 (公司燒錢中),DCF 結果僅供參考")
        cv = company.fcf_volatility
        if cv is not None and cv > 0.30:
            warnings.append(
                f"基準 FCF 歷史波動大 (變異係數 {cv:.0%}),可能含一次性項目,"
                f"DCF 對基準值敏感,建議手動正規化"
            )

        def build(scn: str) -> ScenarioDCF:
            g = growth[scn]
            tg = P.TERMINAL_GROWTH[scn]
            # 硬約束: 終值成長必須 < WACC,否則 Gordon 公式發散
            if tg >= wacc:
                tg_safe = max(wacc - 0.005, 0.0)
                warnings.append(
                    f"{scn}: 終值成長 {tg:.1%} ≥ WACC {wacc:.1%},已下修至 {tg_safe:.1%}"
                )
                tg = tg_safe
            ev, tv_share = _discount(base_fcf, g, tg, wacc, years)
            equity = ev - net_debt
            target = round(equity / shares, 2) if shares else 0.0
            ret = round(target / price - 1, 4) if price else 0.0
            if tv_share > P.TV_SHARE_WARN:
                warnings.append(
                    f"{scn}: 終值佔企業價值 {tv_share:.0%} (>{P.TV_SHARE_WARN:.0%}),"
                    f"此 DCF 實質在猜終值"
                )
            return ScenarioDCF(
                growth=round(g, 4), terminal_growth=round(tg, 4),
                target=target, ret=ret,
                ev=round(ev, 0), equity_value=round(equity, 0),
                tv_share=round(tv_share, 3),
            )

        bear = build("bear")
        base = build("base")
        bull = build("bull")

        sensitivity = self._sensitivity(
            base_fcf, growth["base"], wacc, years, net_debt, shares
        )

        rationale = (
            f"FCF 折現法。基準 FCF=${base_fcf / 1e9:.2f}B,WACC={wacc:.1%},"
            f"明確預測 {years} 年。成長假設: {growth_src}。"
            f"三情境僅變動 FCF 成長率與終值成長,WACC 共用。"
        )

        # 與分析師均價對照
        if company.analyst_target_mean and base.target:
            diff = base.target / company.analyst_target_mean - 1
            if abs(diff) > 0.30:
                warnings.append(
                    f"DCF Base (${base.target}) 與分析師均價 "
                    f"(${company.analyst_target_mean:.0f}) 差異 {diff:+.0%},假設可能需調整"
                )

        return DCFResult(
            ticker=company.ticker, name=company.name,
            current_price=price, base_fcf=base_fcf,
            fcf_source=company.fcf_source,
            shares_outstanding=shares, net_debt=net_debt,
            wacc=wacc_res, projection_years=years,
            bear=bear, base=base, bull=bull,
            sensitivity=sensitivity, rationale=rationale,
            sector=company.sector, industry=company.industry,
            analyst_target_mean=company.analyst_target_mean,
            warnings=warnings,
        )

    def _sensitivity(self, base_fcf, base_g, wacc, years, net_debt, shares):
        """以 Base 情境為中心,WACC × 終值成長 各擾動 → 每股目標價矩陣"""
        rows = []
        for dw in P.SENSITIVITY_WACC_STEPS:
            w = wacc + dw
            row = {"wacc": round(w, 4), "values": []}
            for dtg in P.SENSITIVITY_TG_STEPS:
                tg = P.TERMINAL_GROWTH["base"] + dtg
                if tg >= w:                       # 公式會發散,留空
                    row["values"].append(None)
                    continue
                ev, _ = _discount(base_fcf, base_g, tg, w, years)
                equity = ev - net_debt
                target = round(equity / shares, 2) if shares else 0.0
                row["values"].append(target)
            rows.append(row)
        return rows
