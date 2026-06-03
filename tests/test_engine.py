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

    assert any("虧損" in w for w in r.warnings)
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
    assert any("分析師" in w for w in r.warnings)
    print("✓ test_analyst_divergence_warning")


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
    ]
    print("執行測試...\n")
    for t in tests:
        t()
    print(f"\n✅ 全部 {len(tests)} 個測試通過")


if __name__ == "__main__":
    run_all()
