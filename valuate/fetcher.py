"""
fetcher.py
==========
從 yfinance 抓取單一公司的估值所需資料。

抓取項目:
  - 公司基本資訊 (名稱 / sector / industry)
  - 現價
  - Forward EPS / Trailing EPS
  - Forward P/E / Trailing P/E
  - 市值 / 流通股數
  - 分析師目標價 (供參考)

僅支援美股 (依使用者決定的範圍)。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

try:
    import yfinance as yf
except ImportError:
    raise ImportError("缺少 yfinance,請執行: pip install yfinance")


@dataclass
class CompanyData:
    """單一公司的估值輸入資料"""
    ticker: str
    name: str = ""
    sector: Optional[str] = None
    industry: Optional[str] = None

    current_price: Optional[float] = None
    forward_eps: Optional[float] = None
    trailing_eps: Optional[float] = None
    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    market_cap: Optional[float] = None
    shares_outstanding: Optional[float] = None

    # 分析師資料 (供對照)
    analyst_target_mean: Optional[float] = None
    analyst_target_high: Optional[float] = None
    analyst_target_low: Optional[float] = None
    recommendation: Optional[str] = None

    fetch_errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """至少要有現價 + (forward 或 trailing EPS) 才能估值"""
        has_eps = self.forward_eps is not None or self.trailing_eps is not None
        return self.current_price is not None and has_eps

    @property
    def best_eps(self) -> Optional[float]:
        """優先用 forward EPS,沒有才用 trailing"""
        return self.forward_eps if self.forward_eps else self.trailing_eps


def _safe_get(info: dict, key: str) -> Optional[float]:
    """從 info dict 安全取數值"""
    v = info.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_company(ticker: str) -> CompanyData:
    """
    抓取單一公司完整估值資料。

    Args:
        ticker: 股票代號 (如 "AVGO", "NVDA")

    Returns:
        CompanyData (即使部分欄位抓不到也會回傳,檢查 is_valid)
    """
    ticker = ticker.strip().upper()
    data = CompanyData(ticker=ticker)

    try:
        t = yf.Ticker(ticker)
    except Exception as e:
        data.fetch_errors.append(f"無法建立 Ticker 物件: {e}")
        return data

    # 現價: fast_info 優先 (快又穩)
    try:
        price = t.fast_info.get("last_price")
        if price is None:
            hist = t.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        data.current_price = float(price) if price else None
    except Exception as e:
        data.fetch_errors.append(f"現價抓取失敗: {e}")

    # 其餘資料來自 info (較慢但完整)
    try:
        info = t.info
    except Exception as e:
        data.fetch_errors.append(f"info 抓取失敗: {e}")
        info = {}

    if info:
        data.name = info.get("longName") or info.get("shortName") or ticker
        data.sector = info.get("sector")
        data.industry = info.get("industry")

        data.forward_eps = _safe_get(info, "forwardEps")
        data.trailing_eps = _safe_get(info, "trailingEps")
        data.forward_pe = _safe_get(info, "forwardPE")
        data.trailing_pe = _safe_get(info, "trailingPE")
        data.market_cap = _safe_get(info, "marketCap")
        data.shares_outstanding = _safe_get(info, "sharesOutstanding")

        data.analyst_target_mean = _safe_get(info, "targetMeanPrice")
        data.analyst_target_high = _safe_get(info, "targetHighPrice")
        data.analyst_target_low = _safe_get(info, "targetLowPrice")
        data.recommendation = info.get("recommendationKey")

        # 現價 fallback: 若 fast_info 失敗,用 info 的
        if data.current_price is None:
            data.current_price = _safe_get(info, "currentPrice")

    return data
