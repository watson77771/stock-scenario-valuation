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
    raise ImportError("yfinance not installed. Run: pip install yfinance")


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
    financial_currency: Optional[str] = None       # 財報幣別 (ADR 可能非 USD)
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
        """歷史 FCF 複合成長率 (需 >=2 個正值;fcf_history 約定為舊→新)。

        注意: 只取頭尾兩點,對端點雜訊極敏感 (最新年 capex 暴增就會算出假性負成長)。
        DCF 引擎優先用 fcf_growth_robust;此屬性保留供對照與向後相容。
        """
        h = [x for x in self.fcf_history if x and x > 0]
        if len(h) < 2:
            return None
        try:
            return (h[-1] / h[0]) ** (1 / (len(h) - 1)) - 1
        except (ValueError, ZeroDivisionError):
            return None

    @property
    def fcf_growth_robust(self) -> Optional[float]:
        """穩健的歷史 FCF 成長率 = 逐年 YoY 成長率的「中位數」。

        相較 fcf_cagr 只看頭尾兩點,中位數對單一年度的 capex 高峰 / 一次性項目
        更不敏感 (一個離群年份不會主導結果),作為 DCF Base 成長錨更可靠。
        需至少 2 個相鄰、皆為正的 FCF 才計算;資料不足回 None。
        """
        h = [x for x in self.fcf_history if x is not None]
        yoy = []
        for prev, cur in zip(h, h[1:]):
            if prev and prev > 0 and cur and cur > 0:
                yoy.append(cur / prev - 1)
        if not yoy:
            return None
        yoy.sort()
        n = len(yoy)
        mid = n // 2
        return yoy[mid] if n % 2 else (yoy[mid - 1] + yoy[mid]) / 2

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


def _fx_to_usd(currency: str) -> Optional[float]:
    """取得 1 單位外幣 = 多少 USD。USD 回 1.0;抓不到回 None。"""
    if not currency or currency == "USD":
        return 1.0
    try:
        fx = yf.Ticker(f"{currency}USD=X")
        rate = fx.fast_info.get("last_price")
        if rate is None:
            hist = fx.history(period="5d")
            if not hist.empty:
                rate = float(hist["Close"].iloc[-1])
        return float(rate) if rate else None
    except Exception:
        return None


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
            return P.RISK_FREE_FALLBACK, f"^TNX unavailable; using fallback Rf={P.RISK_FREE_FALLBACK:.1%}"
        raw = float(raw)
        # ^TNX unit handling: may report 4.3 (%) or legacy 43.0 (x10)
        rate = raw / 1000 if raw > 25 else raw / 100
        return round(rate, 4), f"10Y UST ^TNX={raw:g} -> Rf={rate:.2%}"
    except Exception as e:
        return P.RISK_FREE_FALLBACK, f"^TNX fetch failed ({e}); using fallback Rf={P.RISK_FREE_FALLBACK:.1%}"


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
        data.fetch_errors.append(f"Failed to create Ticker object: {e}")
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
        data.fetch_errors.append(f"Price fetch failed: {e}")

    # 其餘資料來自 info (較慢但完整)
    try:
        info = t.info
    except Exception as e:
        data.fetch_errors.append(f"info fetch failed: {e}")
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
            data.fetch_errors.append(f"Cash-flow statement fetch failed: {e}")

        # 基準 FCF: 優先用年度現金流量表最新值 (比 info TTM 穩定),否則退回 info TTM
        if data.fcf_history:
            data.free_cashflow = data.fcf_history[-1]
            data.fcf_source = "latest annual cash-flow statement"
            # 與 info TTM 對照,差異大代表近期可能有一次性項目
            if (info_fcf and data.free_cashflow
                    and abs(info_fcf / data.free_cashflow - 1) > 0.25):
                data.fetch_errors.append(
                    f"FCF divergence (annual ${data.free_cashflow / 1e9:.1f}B vs "
                    f"TTM ${info_fcf / 1e9:.1f}B); recent period may include one-off items, manual review advised"
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
            data.fetch_errors.append(f"Income statement fetch failed: {e}")

        # 幣別統一: 財報(可能 TWD/KRW 等) vs 股價(USD)。ADR 常見不一致,
        # 不換算會讓 DCF 結果差數十倍。把所有「絕對金額」換成 USD;
        # 比率類 (稅率) 因分子分母同幣別會自動抵銷,不需換算。
        fin_cur = info.get("financialCurrency") if info else None
        data.financial_currency = fin_cur
        if fin_cur and fin_cur != "USD":
            rate = _fx_to_usd(fin_cur)
            if rate is None:
                data.fetch_errors.append(
                    f"Financials are in {fin_cur} but FX fetch failed; DCF can't be unified to USD, use P/E method")
                data.free_cashflow = None          # block DCF to avoid currency-mixed garbage
            else:
                if data.free_cashflow is not None:
                    data.free_cashflow *= rate
                data.fcf_history = [x * rate for x in data.fcf_history]
                if data.total_debt is not None:
                    data.total_debt *= rate
                if data.total_cash is not None:
                    data.total_cash *= rate
                if data.interest_expense is not None:
                    data.interest_expense *= rate
                data.fcf_source += f" (converted from {fin_cur} to USD)"
                data.fetch_errors.append(
                    f"Financials in {fin_cur} converted to USD (FX {rate:.4f}); "
                    f"ADR valuation carries FX risk, for reference only")

    return data
