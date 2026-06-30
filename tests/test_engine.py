"""
test_engine.py
==============
估值引擎單元測試 (用 mock 資料,不需網路)。

執行: python -m pytest tests/  或  python tests/test_engine.py
"""

import sys
from pathlib import Path

# 讓測試能 import valuate package
sys.path.insert(0, str(Path(__file__).parent.parent))

from valuate.sector_map import get_pe_range, DEFAULT_PE_RANGE
from valuate.assumptions.sector_based import SectorBasedAssumptions
from valuate.engine import ValuationEngine
from valuate.fetcher import CompanyData
from valuate.wacc import compute_wacc
from valuate.dcf import DCFEngine
from valuate.peg import PEGEngine
from valuate.datasources import robust_eps_cagr
import valuate.peg_params as PP


class MockCompany:
    """模擬 CompanyData,避免測試時呼叫 yfinance"""
    def __init__(self, ticker, name, sector, industry, price,
                 fwd_eps=None, trail_eps=None, analyst=None):
        self.ticker = ticker
        self.name = name
        self.sector = sector
        self.industry = industry
        self.current_price = price
        self.forward_eps = fwd_eps
        self.trailing_eps = trail_eps
        self.analyst_target_mean = analyst

    @property
    def is_valid(self):
        has_eps = self.forward_eps is not None or self.trailing_eps is not None
        return self.current_price is not None and has_eps

    @property
    def best_eps(self):
        return self.forward_eps if self.forward_eps else self.trailing_eps


def test_sector_map_industry_match():
    """細分產業優先匹配"""
    pe, label = get_pe_range("Technology", "Semiconductors")
    assert pe.base == 28
    assert "industry" in label
    print("✓ test_sector_map_industry_match")


def test_sector_map_sector_fallback():
    """industry 找不到時退回 sector"""
    pe, label = get_pe_range("Energy", "Some Unknown Industry")
    assert pe.base == 12  # Energy sector base
    assert "sector" in label
    print("✓ test_sector_map_sector_fallback")


def test_sector_map_default():
    """都找不到用通用預設"""
    pe, label = get_pe_range("Nonexistent", "Nonexistent")
    assert pe.base == DEFAULT_PE_RANGE.base
    assert "default" in label
    print("✓ test_sector_map_default")


def test_engine_basic_calc():
    """基本估值計算正確"""
    company = MockCompany("AVGO", "Broadcom", "Technology",
                          "Semiconductors", 433.62, fwd_eps=13.50)
    engine = ValuationEngine(SectorBasedAssumptions())
    r = engine.value(company)

    assert r.base_target == round(13.50 * 28, 2)  # 378.0
    assert r.bear_target == round(13.50 * 18, 2)  # 243.0
    assert r.bull_target == round(13.50 * 40, 2)  # 540.0
    assert r.eps_type == "forward"
    print("✓ test_engine_basic_calc")


def test_engine_return_calc():
    """報酬率計算正確"""
    company = MockCompany("X", "X", "Energy",
                          "Oil & Gas Refining & Marketing", 100.0, fwd_eps=10.0)
    engine = ValuationEngine(SectorBasedAssumptions())
    r = engine.value(company)

    # Energy refining: 8/12/16x, EPS 10 → 80/120/160
    assert r.base_target == 120.0
    assert abs(r.base_return - 0.20) < 0.001  # +20%
    print("✓ test_engine_return_calc")


def test_engine_trailing_fallback():
    """無 forward EPS 時用 trailing 並警示"""
    company = MockCompany("X", "X", "Technology", "Semiconductors",
                          100.0, fwd_eps=None, trail_eps=5.0)
    engine = ValuationEngine(SectorBasedAssumptions())
    r = engine.value(company)

    assert r.eps_type == "trailing"
    assert any("trailing" in w for w in r.warnings)
    print("✓ test_engine_trailing_fallback")


def test_engine_negative_eps_warning():
    """虧損公司應警示"""
    company = MockCompany("X", "X", "Technology", "Software - Application",
                          50.0, fwd_eps=-2.0)
    engine = ValuationEngine(SectorBasedAssumptions())
    r = engine.value(company)

    assert any("loss-making" in w for w in r.warnings)
    print("✓ test_engine_negative_eps_warning")


def test_engine_invalid_company():
    """資料不足應拋錯"""
    company = MockCompany("X", "X", "Technology", "Semiconductors",
                          None, fwd_eps=None)
    engine = ValuationEngine(SectorBasedAssumptions())
    try:
        engine.value(company)
        assert False, "應該拋 ValueError"
    except ValueError:
        print("✓ test_engine_invalid_company")


def test_analyst_divergence_warning():
    """與分析師目標差異過大應警示"""
    # Base 目標會是 13.5×28=378, 分析師設 200, 差異 +89%
    company = MockCompany("AVGO", "Broadcom", "Technology",
                          "Semiconductors", 433.62, fwd_eps=13.50,
                          analyst=200.0)
    engine = ValuationEngine(SectorBasedAssumptions())
    r = engine.value(company)
    assert any("analyst" in w for w in r.warnings)
    print("✓ test_analyst_divergence_warning")


# ============================================================
# 階段二 DCF 測試 (用真實 CompanyData 直接賦值,不呼叫 yfinance)
# ============================================================

def make_dcf_company(**kw):
    """建一個帶 DCF 欄位的 CompanyData (預設: 100 元、10 億 FCF、1 億股、無負債)"""
    c = CompanyData(ticker=kw.get("ticker", "X"))
    c.name = kw.get("name", "X")
    c.current_price = kw.get("price", 100.0)
    c.shares_outstanding = kw.get("shares", 1e8)
    c.market_cap = kw.get("market_cap", c.current_price * c.shares_outstanding)
    c.free_cashflow = kw.get("fcf", 1e9)
    c.fcf_source = "mock"
    c.total_debt = kw.get("total_debt", 0.0)
    c.total_cash = kw.get("total_cash", 0.0)
    c.beta = kw.get("beta", 1.0)
    c.interest_expense = kw.get("interest", None)
    c.pretax_income = kw.get("pretax", None)
    c.tax_provision = kw.get("tax", None)
    c.fcf_history = kw.get("fcf_history", [])
    c.analyst_target_mean = kw.get("analyst", None)
    c.sector = kw.get("sector", "Technology")
    c.industry = kw.get("industry", "Software - Application")
    return c


def test_dcf_basic_ordering():
    """DCF 基本: 目標價為正,且 Bull > Base > Bear"""
    r = DCFEngine(risk_free_rate=0.04).value(make_dcf_company())
    assert r.base.target > 0
    assert r.bull.target > r.base.target > r.bear.target
    print("✓ test_dcf_basic_ordering")


def test_dcf_tv_share_in_range():
    """終值佔比應介於 0 與 1 之間"""
    r = DCFEngine(0.04).value(make_dcf_company())
    for s in (r.bear, r.base, r.bull):
        assert 0 < s.tv_share < 1
    print("✓ test_dcf_tv_share_in_range")


def test_dcf_terminal_below_wacc_enforced():
    """終值成長必被壓在 WACC 以下 (否則 Gordon 公式發散)"""
    r = DCFEngine(0.04).value(make_dcf_company())
    assert r.base.terminal_growth < r.wacc.wacc
    print("✓ test_dcf_terminal_below_wacc_enforced")


def test_dcf_invalid_company():
    """缺 FCF 應拋 ValueError"""
    c = make_dcf_company(fcf=None)
    try:
        DCFEngine(0.04).value(c)
        assert False, "應該拋 ValueError"
    except ValueError:
        print("✓ test_dcf_invalid_company")


def test_wacc_no_debt_equals_cost_of_equity():
    """無負債時 WACC 應等於股權成本"""
    w = compute_wacc(make_dcf_company(total_debt=0.0), rf=0.04)
    assert abs(w.wacc - w.cost_of_equity) < 1e-9
    print("✓ test_wacc_no_debt_equals_cost_of_equity")


def test_wacc_beta_blume_clamp():
    """高 beta 經 Blume 調整後仍被夾擠到上限 1.6"""
    # Blume: 0.67*3.0 + 0.33*1.0 = 2.34 → clamp 至 1.6 (上限由 2.0 收緊)
    w = compute_wacc(make_dcf_company(beta=3.0), rf=0.04)
    assert w.beta_adj == 1.6
    print("✓ test_wacc_beta_blume_clamp")


def test_wacc_tax_from_statement():
    """有效稅率由損益表推算 (所得稅/稅前淨利)"""
    w = compute_wacc(make_dcf_company(pretax=1000.0, tax=200.0,
                                      total_debt=500.0, interest=25.0), rf=0.04)
    assert abs(w.tax_rate - 0.20) < 1e-9
    print("✓ test_wacc_tax_from_statement")


def test_fcf_cagr_property():
    """歷史 FCF CAGR 計算正確 (100→200, 2 期 → ~41.4%)"""
    c = make_dcf_company(fcf_history=[100.0, 141.42, 200.0])
    assert abs(c.fcf_cagr - 0.4142) < 0.001
    print("✓ test_fcf_cagr_property")


# ============================================================
# 階段二 DCF 校準修正測試 (兩段式 fade + 終值雙軌 + 正規化)
# ============================================================

def test_fcf_growth_robust_median():
    """穩健成長 = YoY 中位數,對單一離群年份不敏感"""
    # YoY: 100→110 (+10%), 110→121 (+10%), 121→60 (capex 暴增, -50.4%)
    # 中位數 = +10%;若用頭尾 CAGR 會是負的 (100→60),被離群年份主導
    c = make_dcf_company(fcf_history=[100.0, 110.0, 121.0, 60.0])
    assert abs(c.fcf_growth_robust - 0.10) < 0.01
    assert c.fcf_cagr is None or c.fcf_cagr < c.fcf_growth_robust
    print("✓ test_fcf_growth_robust_median")


def test_dcf_base_fcf_normalized_median():
    """基準 FCF 取近年中位數,單一被壓低的最新年度不會主導估值"""
    # 最新年度 5 億 (capex 高峰),前兩年各 10 億 → 中位數 = 10 億
    c = make_dcf_company(fcf=5e8, fcf_history=[1e9, 1e9, 5e8])
    r = DCFEngine(0.04).value(c)
    # 正規化基準應 > 最新年度 5 億 (用了中位數,而非單一最新年度)
    assert r.base_fcf > 5e8
    # 且應觸發「正規化偏離」警示
    assert any("Normalized" in w for w in r.warnings)
    print("✓ test_dcf_base_fcf_normalized_median")


def test_dcf_fade_reduces_explosiveness():
    """兩段式 fade: 高起始成長不會讓估值無限爆衝 (成長率逐年衰減至終值)"""
    high = make_dcf_company(fcf=1e9, fcf_history=[4e8, 6e8, 9e8, 1e9])  # 高歷史成長
    r = DCFEngine(0.04).value(high)
    # 即使起始成長被夾到上限 25%,fade 後 Bull 仍應有限 (不會出現天文數字)
    assert r.bull.target < 10 * r.current_price
    assert r.bull.target > r.base.target > r.bear.target > 0
    print("✓ test_dcf_fade_reduces_explosiveness")


def test_dcf_dual_terminal_lifts_value():
    """終值雙軌 (混入出場倍數) 使隱含終值倍數高於純 Gordon 的 ~13x 下限"""
    r = DCFEngine(0.04).value(make_dcf_company())
    # Base 出場倍數 18x;混合後實際隱含倍數應落在 Gordon(~13x) 與 18x 之間,明顯 >13
    assert r.base.implied_terminal_multiple > 13.0
    assert r.base.exit_multiple == 18.0
    print("✓ test_dcf_dual_terminal_lifts_value")


# ============================================================
# 階段二+ PEG 成長校正法測試 (離線,mock 資料)
# ============================================================

def make_peg_company(price=100.0, trailing_eps=5.0, forward_eps=5.0,
                     sector="Technology", industry="Software - Application",
                     analyst=None):
    c = CompanyData(ticker="X")
    c.name = "X"
    c.current_price = price
    c.trailing_eps = trailing_eps
    c.forward_eps = forward_eps
    c.sector = sector
    c.industry = industry
    c.analyst_target_mean = analyst
    return c


def test_robust_eps_cagr_median():
    """穩健 EPS 成長 = YoY 中位數 (每年 +10% → 10%)"""
    g = robust_eps_cagr([100, 110, 121, 133.1])
    assert abs(g - 0.10) < 0.001
    print("✓ test_robust_eps_cagr_median")


def test_peg_ratios_basic():
    """trailing / forward PEG 計算正確"""
    c = make_peg_company(price=100, trailing_eps=5, forward_eps=5)
    hist = [100, 110, 121, 133.1]                    # 歷史成長 10%
    fwd = {"forward_eps": 5.0, "growth": 0.20, "eps_series": [5, 6, 7.2], "n_years": 3}
    r = PEGEngine().value(c, eps_history=hist, fwd_estimates=fwd)
    assert r.trailing_pe == 20.0
    assert abs(r.trailing_peg - 2.0) < 0.01          # 20 / 10
    assert r.forward_pe == 20.0
    assert abs(r.forward_peg - 1.0) < 0.01           # 20 / 20
    print("✓ test_peg_ratios_basic")


def test_peg_growth_justified_target():
    """成長校正目標價 = (成長% × 目標PEG) × EPS"""
    c = make_peg_company(price=100, trailing_eps=5, forward_eps=5)
    fwd = {"forward_eps": 5.0, "growth": 0.20, "eps_series": [5, 6, 7.2], "n_years": 3}
    r = PEGEngine().value(c, eps_history=None, fwd_estimates=fwd)
    # 用未來成長 20%,EPS 5。Base PEG 1.5 → 合理 PE = 20*1.5 = 30 → 目標 150
    assert abs(r.base.fair_pe - 30.0) < 0.1
    assert abs(r.base.target - 150.0) < 0.1
    assert abs(r.bear.target - 100.0) < 0.1          # PEG 1.0 → PE 20 → 100
    assert abs(r.bull.target - 200.0) < 0.1          # PEG 2.0 → PE 40 → 200
    assert r.applicable
    print("✓ test_peg_growth_justified_target")


def test_peg_gating_low_growth():
    """低成長 (<5%) 應 gating 為不適用並警示"""
    c = make_peg_company(price=100, trailing_eps=5, forward_eps=5)
    fwd = {"forward_eps": 5.0, "growth": 0.02, "eps_series": [5, 5.1, 5.2], "n_years": 3}
    r = PEGEngine().value(c, fwd_estimates=fwd)
    assert r.applicable is False
    assert any("Low growth" in w for w in r.warnings)
    print("✓ test_peg_gating_low_growth")


def test_peg_gating_negative_eps():
    """虧損 (EPS≤0) 應不適用,且不產目標價"""
    c = make_peg_company(price=100, trailing_eps=-2.0, forward_eps=None)
    r = PEGEngine().value(c, fwd_estimates=None)
    assert r.applicable is False
    assert r.base is None
    assert any("loss-making" in w for w in r.warnings)
    print("✓ test_peg_gating_negative_eps")


def test_peg_gating_cyclical_sector_warns():
    """景氣循環/金融產業應標適用性警示"""
    c = make_peg_company(sector="Energy", industry="Oil & Gas E&P")
    fwd = {"forward_eps": 5.0, "growth": 0.15, "eps_series": [5, 6, 7], "n_years": 3}
    r = PEGEngine().value(c, fwd_estimates=fwd)
    assert any("weak reference value" in w for w in r.warnings)
    print("✓ test_peg_gating_cyclical_sector_warns")


def test_peg_high_growth_clamped():
    """超高成長 (>50%) 應警示且成長率夾至上限算目標價"""
    c = make_peg_company(price=100, trailing_eps=5, forward_eps=5)
    fwd = {"forward_eps": 5.0, "growth": 0.80, "eps_series": [5, 7, 9], "n_years": 3}
    r = PEGEngine().value(c, fwd_estimates=fwd)
    assert any("Very high growth" in w for w in r.warnings)
    assert r.growth_used <= PP.GROWTH_CLAMP[1] + 1e-9   # 夾至 0.40
    print("✓ test_peg_high_growth_clamped")


def run_all():
    """跑全部測試"""
    tests = [
        test_sector_map_industry_match,
        test_sector_map_sector_fallback,
        test_sector_map_default,
        test_engine_basic_calc,
        test_engine_return_calc,
        test_engine_trailing_fallback,
        test_engine_negative_eps_warning,
        test_engine_invalid_company,
        test_analyst_divergence_warning,
        # --- 階段二 DCF ---
        test_dcf_basic_ordering,
        test_dcf_tv_share_in_range,
        test_dcf_terminal_below_wacc_enforced,
        test_dcf_invalid_company,
        test_wacc_no_debt_equals_cost_of_equity,
        test_wacc_beta_blume_clamp,
        test_wacc_tax_from_statement,
        test_fcf_cagr_property,
        # --- 階段二 DCF 校準修正 ---
        test_fcf_growth_robust_median,
        test_dcf_base_fcf_normalized_median,
        test_dcf_fade_reduces_explosiveness,
        test_dcf_dual_terminal_lifts_value,
        # --- 階段二+ PEG 成長校正法 ---
        test_robust_eps_cagr_median,
        test_peg_ratios_basic,
        test_peg_growth_justified_target,
        test_peg_gating_low_growth,
        test_peg_gating_negative_eps,
        test_peg_gating_cyclical_sector_warns,
        test_peg_high_growth_clamped,
    ]
    print("執行測試...\n")
    for t in tests:
        t()
    print(f"\n✅ 全部 {len(tests)} 個測試通過")


if __name__ == "__main__":
    run_all()
