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
    growth: float            # FCF 起始成長率 g (明確期第 1 年,之後 fade 至終值成長)
    terminal_growth: float   # 終值成長 g_終 (Gordon 永續用)
    target: float            # 每股目標價
    ret: float               # 相對現價報酬率
    ev: float                # 企業價值 (Enterprise Value)
    equity_value: float      # 股權價值 = EV − 淨負債
    tv_share: float          # 終值現值佔 EV 比 (健檢用)
    exit_multiple: float = 0.0            # 出場 EV/FCF 倍數 (終值雙軌之一的輸入)
    implied_terminal_multiple: float = 0.0  # 混合後終值 ÷ 末年 FCF = 實際隱含倍數


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


def _project_fcf(base_fcf: float, g_start: float, g_terminal: float,
                 years: int) -> list[float]:
    """
    產生明確期各年 FCF。兩段式 (fade): 成長率由 g_start (第 1 年) 線性衰減至
    g_terminal (第 N 年),反映企業成長隨規模遞減。FADE_TO_TERMINAL 關閉時退回
    全期固定 g_start。
    """
    fcfs = []
    fcf = base_fcf
    for t in range(1, years + 1):
        if P.FADE_TO_TERMINAL and years > 1:
            g_t = g_start + (g_terminal - g_start) * (t - 1) / (years - 1)
        else:
            g_t = g_start
        fcf = fcf * (1 + g_t)
        fcfs.append(fcf)
    return fcfs


def _discount(base_fcf: float, g_start: float, terminal_growth: float,
              wacc: float, years: int, exit_multiple: float,
              blend: float) -> tuple[float, float, float]:
    """
    把 FCF 折現成企業價值,終值採「Gordon 永續 × 出場倍數」雙軌加權。

    Args:
        g_start:        明確期起始成長率 (之後 fade 至 terminal_growth)
        exit_multiple:  出場 EV/FCF 倍數 (終值另一軌)
        blend:          Gordon 權重 (0=全出場倍數, 1=全 Gordon)

    Returns:
        (ev, tv_share, implied_terminal_multiple)
        implied_terminal_multiple = 混合終值 ÷ 末年 FCF,供透明檢視實際隱含倍數
    """
    fcfs = _project_fcf(base_fcf, g_start, terminal_growth, years)
    pv_explicit = sum(f / (1 + wacc) ** (t + 1) for t, f in enumerate(fcfs))
    fcf_n = fcfs[-1]

    # 終值雙軌
    tv_gordon = fcf_n * (1 + terminal_growth) / (wacc - terminal_growth)
    tv_exit = fcf_n * exit_multiple
    tv = blend * tv_gordon + (1 - blend) * tv_exit
    pv_tv = tv / (1 + wacc) ** years

    ev = pv_explicit + pv_tv
    tv_share = pv_tv / ev if ev else 0.0
    implied_mult = tv / fcf_n if fcf_n else 0.0
    return ev, tv_share, implied_mult


def _normalized_base_fcf(company) -> tuple[float, str, float | None]:
    """
    正規化基準 FCF: 取最近 N 年 FCF 的中位數,抵銷單一年度 capex 高峰 / 一次性項目。
    歷史不足時退回 company.free_cashflow (最新年度或 TTM)。

    Returns:
        (base_fcf, 來源說明, 最新年度值)  最新年度值供「正規化偏離」警示對照
    """
    import statistics
    latest = company.free_cashflow
    hist = [x for x in company.fcf_history if x is not None]
    if len(hist) >= 2:
        recent = hist[-P.FCF_NORMALIZE_YEARS:]
        pos = [x for x in recent if x > 0]
        if len(pos) >= 2:
            norm = statistics.median(pos)
            src = (f"{len(pos)}-yr median-normalized FCF "
                   f"(${norm / 1e9:.2f}B; latest yr ${(latest or 0) / 1e9:.2f}B)")
            return norm, src, latest
    return latest, company.fcf_source or "latest yr/TTM", latest


def _derive_growth(company) -> tuple[dict, str]:
    """
    決定三情境 FCF「起始」成長率 (明確期第 1 年,之後 fade 至終值成長)。
    優先用穩健成長 (中位數 YoY) 當 Base 錨,其次用頭尾 CAGR,皆無則用產業通用預設。
    """
    robust = company.fcf_growth_robust
    if robust is not None:
        base_g = _clamp(robust, *P.GROWTH_CLAMP)
        bear_g = _clamp(base_g - P.GROWTH_SPREAD_DOWN, *P.GROWTH_CLAMP)
        bull_g = _clamp(base_g + P.GROWTH_SPREAD_UP, *P.GROWTH_CLAMP)
        return ({"bear": bear_g, "base": base_g, "bull": bull_g},
                f"historical robust FCF growth (median YoY) {robust:+.1%} as Base anchor")
    cagr = company.fcf_cagr
    if cagr is not None:
        base_g = _clamp(cagr, *P.GROWTH_CLAMP)
        bear_g = _clamp(base_g - P.GROWTH_SPREAD_DOWN, *P.GROWTH_CLAMP)
        bull_g = _clamp(base_g + P.GROWTH_SPREAD_UP, *P.GROWTH_CLAMP)
        return ({"bear": bear_g, "base": base_g, "bull": bull_g},
                f"historical FCF CAGR {cagr:+.1%} as Base anchor (median YoY unavailable)")
    return dict(P.DEFAULT_GROWTH), "insufficient FCF history; using generic growth defaults"


class DCFEngine:
    """FCF 折現估值引擎"""

    def __init__(self, risk_free_rate: float):
        self.rf = risk_free_rate

    def value(self, company) -> DCFResult:
        if not company.has_dcf_data:
            raise ValueError(
                f"{company.ticker} missing required DCF data "
                f"(FCF={company.free_cashflow}, shares={company.shares_outstanding}, "
                f"price={company.current_price})"
            )

        base_fcf, fcf_src, latest_fcf = _normalized_base_fcf(company)
        wacc_res = compute_wacc(company, self.rf)
        wacc = wacc_res.wacc
        years = P.PROJECTION_YEARS
        blend = P.TERMINAL_METHOD_BLEND
        shares = company.shares_outstanding
        net_debt = company.net_debt or 0.0
        price = company.current_price

        growth, growth_src = _derive_growth(company)

        warnings = list(wacc_res.notes)
        if base_fcf <= 0:
            warnings.append("Base FCF <= 0 (company burning cash); DCF results for reference only")
        # Normalization-divergence warning: large gap vs latest year -> possible one-off / capex peak
        if (latest_fcf and base_fcf and latest_fcf > 0
                and abs(base_fcf / latest_fcf - 1) > P.FCF_NORMALIZE_DIVERGENCE_WARN):
            warnings.append(
                f"Normalized base FCF (${base_fcf / 1e9:.2f}B) vs latest year "
                f"(${latest_fcf / 1e9:.2f}B) differ {base_fcf / latest_fcf - 1:+.0%}; "
                f"recent FCF may include a capex peak / one-off item, buffered with median, manual review advised"
            )
        cv = company.fcf_volatility
        if cv is not None and cv > 0.30:
            warnings.append(
                f"Base FCF history is volatile (CV {cv:.0%}); may include one-off items. "
                f"DCF is sensitive to the base; median-normalized but manual review advised"
            )

        def build(scn: str) -> ScenarioDCF:
            g = growth[scn]
            tg = P.TERMINAL_GROWTH[scn]
            exit_m = P.EXIT_FCF_MULTIPLE[scn]
            # 硬約束: 終值成長必須 < WACC,否則 Gordon 公式發散
            if tg >= wacc:
                tg_safe = max(wacc - 0.005, 0.0)
                warnings.append(
                    f"{scn}: terminal growth {tg:.1%} >= WACC {wacc:.1%}, downshifted to {tg_safe:.1%}"
                )
                tg = tg_safe
            ev, tv_share, impl_mult = _discount(
                base_fcf, g, tg, wacc, years, exit_m, blend)
            equity = ev - net_debt
            target = round(equity / shares, 2) if shares else 0.0
            ret = round(target / price - 1, 4) if price else 0.0
            if tv_share > P.TV_SHARE_WARN:
                warnings.append(
                    f"{scn}: terminal value is {tv_share:.0%} of EV (>{P.TV_SHARE_WARN:.0%}); "
                    f"this DCF is essentially guessing the terminal value"
                )
            return ScenarioDCF(
                growth=round(g, 4), terminal_growth=round(tg, 4),
                target=target, ret=ret,
                ev=round(ev, 0), equity_value=round(equity, 0),
                tv_share=round(tv_share, 3),
                exit_multiple=round(exit_m, 1),
                implied_terminal_multiple=round(impl_mult, 1),
            )

        bear = build("bear")
        base = build("base")
        bull = build("bull")

        sensitivity = self._sensitivity(
            base_fcf, growth["base"], wacc, years, net_debt, shares
        )

        rationale = (
            f"FCF DCF (two-stage fade + dual-track terminal). Base FCF=${base_fcf / 1e9:.2f}B "
            f"({fcf_src}), WACC={wacc:.1%}, {years}-yr explicit forecast, growth fades from the "
            f"starting rate to terminal growth. Growth assumption: {growth_src}. Terminal = Gordon "
            f"perpetuity × {blend:.0%} + exit EV/FCF multiple × {1 - blend:.0%} "
            f"(Base exit {P.EXIT_FCF_MULTIPLE['base']:.0f}x, implied {base.implied_terminal_multiple:.0f}x). "
            f"Scenarios vary starting growth, terminal growth and exit multiple; WACC shared."
        )

        # 與分析師均價對照
        if company.analyst_target_mean and base.target:
            diff = base.target / company.analyst_target_mean - 1
            if abs(diff) > 0.30:
                warnings.append(
                    f"DCF Base (${base.target}) vs analyst avg "
                    f"(${company.analyst_target_mean:.0f}) differ {diff:+.0%}; assumptions may need review"
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
        """以 Base 情境為中心,WACC × 終值成長 各擾動 → 每股目標價矩陣。
        終值仍走雙軌混合 (出場倍數固定),故對終值成長的敏感度被刻意緩衝。"""
        exit_m = P.EXIT_FCF_MULTIPLE["base"]
        blend = P.TERMINAL_METHOD_BLEND
        rows = []
        for dw in P.SENSITIVITY_WACC_STEPS:
            w = wacc + dw
            row = {"wacc": round(w, 4), "values": []}
            for dtg in P.SENSITIVITY_TG_STEPS:
                tg = P.TERMINAL_GROWTH["base"] + dtg
                if tg >= w:                       # Gordon 那一軌會發散,留空
                    row["values"].append(None)
                    continue
                ev, _, _ = _discount(base_fcf, base_g, tg, w, years, exit_m, blend)
                equity = ev - net_debt
                target = round(equity / shares, 2) if shares else 0.0
                row["values"].append(target)
            rows.append(row)
        return rows
