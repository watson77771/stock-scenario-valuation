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

    # --- 階段二 DCF 所需 (僅在 fetch_dcf=True 時抓取) ---
    beta: Optional[float] = None
    total_debt: Optional[float] = None
    total_cash: Optional[float] = None
    free_cashflow: Optional[float] = None          # 基準 FCF (TTM 或最新年度)
    fcf_source: str = ""                            # FCF 來源說明
    fcf_history: list[float] = field(default_factory=list)  # 歷史 FCF (舊→新)
    interest_expense: Optional[float] = None
    pretax_income: Optional[float] = None
    tax_provision: Optional[float] = None

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

    # --- 階段二 DCF 衍生屬性 ---
    @property
    def net_debt(self) -> Optional[float]:
        """淨負債 = 總負債 − 現金 (兩者全無時回 None)"""
        if self.total_debt is None and self.total_cash is None:
            return None
        return (self.total_debt or 0.0) - (self.total_cash or 0.0)

    @property
    def effective_tax_rate(self) -> Optional[float]:
        """有效稅率 = 所得稅 / 稅前淨利 (資料不足回 None,由 wacc 後備)"""
        if (self.pretax_income and self.tax_provision is not None
                and self.pretax_income != 0):
            return self.tax_provision / self.pretax_income
        return None

    @property
    def fcf_volatility(self) -> Optional[float]:
        """歷史 FCF 變異係數 (母體標準差 / |平均|);資料不足回 None"""
        h = self.fcf_history
        if len(h) < 2:
            return None
        mean = sum(h) / len(h)
        if mean == 0:
            return None
        var = sum((x - mean) ** 2 for x in h) / len(h)
        return (var ** 0.5) / abs(mean)

    @property
    def fcf_cagr(self) -> Optional[float]:
        """歷史 FCF 複合成長率 (需 >=2 個正值;fcf_history 約定為舊→新)"""
        h = [x for x in self.fcf_history if x and x > 0]
        if len(h) < 2:
            return None
        try:
            return (h[-1] / h[0]) ** (1 / (len(h) - 1)) - 1
        except (ValueError, ZeroDivisionError):
            return None

    @property
    def has_dcf_data(self) -> bool:
        """DCF 至少要有現價 + 基準 FCF + 流通股數"""
        return (self.current_price is not None
                and self.free_cashflow is not None
                and bool(self.shares_outstanding))


def _safe_get(info: dict, key: str) -> Optional[float]:
    """從 info dict 安全取數值"""
    v = info.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _stmt_latest(df, *names) -> Optional[float]:
    """從財報 DataFrame 取第一個匹配 row 的最新 (最左欄) 值"""
    if df is None or getattr(df, "empty", True):
        return None
    for name in names:
        if name in df.index:
            row = df.loc[name].dropna()
            if not row.empty:
                try:
                    return float(row.iloc[0])      # 欄位通常新→舊,取最左 = 最新
                except (TypeError, ValueError):
                    return None
    return None


def _stmt_series(df, *names) -> list[float]:
    """從財報 DataFrame 取某 row 的完整序列 (新→舊)"""
    if df is None or getattr(df, "empty", True):
        return []
    for name in names:
        if name in df.index:
            row = df.loc[name].dropna()
            if not row.empty:
                try:
                    return [float(v) for v in row.values]
                except (TypeError, ValueError):
                    return []
    return []


def _fcf_history_from_cashflow(cf) -> list[float]:
    """從現金流量表組出歷史 FCF 序列 (舊→新)"""
    if cf is None or getattr(cf, "empty", True):
        return []
    # 1. 新版 yfinance 直接有 Free Cash Flow row
    direct = _stmt_series(cf, "Free Cash Flow")
    if direct:
        return list(reversed(direct))              # 新→舊 → 舊→新
    # 2. 否則 FCF = 營業現金流 + 資本支出 (CapEx 通常為負值)
    cfo = _stmt_series(cf, "Operating Cash Flow",
                       "Total Cash From Operating Activities")
    capex = _stmt_series(cf, "Capital Expenditure", "Capital Expenditures")
    if cfo and capex:
        n = min(len(cfo), len(capex))
        fcf = [cfo[i] + capex[i] for i in range(n)]
        return list(reversed(fcf))
    return []


def fetch_risk_free_rate() -> tuple[float, str]:
    """
    抓 10 年期美債殖利率 (^TNX) 當無風險利率 Rf。

    Returns:
        (rate, note)  rate 為小數 (如 0.043);note 供終端顯示與人工核對
    """
    from . import dcf_params as P
    try:
        tnx = yf.Ticker("^TNX")
        raw = tnx.fast_info.get("last_price")
        if raw is None:
            hist = tnx.history(period="5d")
            if not hist.empty:
                raw = float(hist["Close"].iloc[-1])
        if raw is None:
            return P.RISK_FREE_FALLBACK, f"無法取得 ^TNX,用後備 Rf={P.RISK_FREE_FALLBACK:.1%}"
        raw = float(raw)
        # ^TNX 單位處理: 可能報 4.3 (%) 或舊制 43.0 (×10)
        rate = raw / 1000 if raw > 25 else raw / 100
        return round(rate, 4), f"10Y 美債 ^TNX={raw:g} → Rf={rate:.2%}"
    except Exception as e:
        return P.RISK_FREE_FALLBACK, f"^TNX 抓取失敗 ({e}),用後備 Rf={P.RISK_FREE_FALLBACK:.1%}"


def fetch_company(ticker: str, fetch_dcf: bool = False) -> CompanyData:
    """
    抓取單一公司完整估值資料。

    Args:
        ticker:    股票代號 (如 "AVGO", "NVDA")
        fetch_dcf: 是否額外抓取 DCF 所需財報 (現金流量表/負債/利息/稅)。
                   預設 False 以維持 P/E 法的速度,只在 --method dcf 時開啟。

    Returns:
        CompanyData (即使部分欄位抓不到也會回傳,檢查 is_valid / has_dcf_data)
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

    # === 階段二: DCF 所需資料 (僅在需要時抓,避免拖慢 P/E 法) ===
    if fetch_dcf:
        info_fcf = None
        if info:
            data.beta = _safe_get(info, "beta")
            data.total_debt = _safe_get(info, "totalDebt")
            data.total_cash = _safe_get(info, "totalCash")
            info_fcf = _safe_get(info, "freeCashflow")     # TTM,僅作後備/對照

        # 歷史 FCF 序列 (舊→新),作為基準 FCF 的「可審計」首選
        try:
            cf = t.cashflow
            series = _fcf_history_from_cashflow(cf)
            if series:
                data.fcf_history = series
        except Exception as e:
            data.fetch_errors.append(f"現金流量表抓取失敗: {e}")

        # 基準 FCF: 優先用年度現金流量表最新值 (比 info TTM 穩定),否則退回 info TTM
        if data.fcf_history:
            data.free_cashflow = data.fcf_history[-1]
            data.fcf_source = "年度現金流量表最新值"
            # 與 info TTM 對照,差異大代表近期可能有一次性項目
            if (info_fcf and data.free_cashflow
                    and abs(info_fcf / data.free_cashflow - 1) > 0.25):
                data.fetch_errors.append(
                    f"FCF 資料分歧 (年度 ${data.free_cashflow / 1e9:.1f}B vs "
                    f"TTM ${info_fcf / 1e9:.1f}B),近期可能含一次性項目,建議手動檢視"
                )
        elif info_fcf is not None:
            data.free_cashflow = info_fcf
            data.fcf_source = "yfinance freeCashflow (TTM)"

        # 損益表: 利息費用 / 稅前淨利 / 所得稅 (供 WACC 算 Rd 與有效稅率)
        try:
            fin = t.financials
            data.interest_expense = _stmt_latest(fin, "Interest Expense")
            data.pretax_income = _stmt_latest(
                fin, "Pretax Income", "Pre Tax Income", "Income Before Tax")
            data.tax_provision = _stmt_latest(
                fin, "Tax Provision", "Income Tax Expense")
        except Exception as e:
            data.fetch_errors.append(f"損益表抓取失敗: {e}")

    return data
