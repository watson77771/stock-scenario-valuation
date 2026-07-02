"""
datasources.py
==============
PEG 所需「成長率」的進階資料源 —— yfinance 免費財報只給約 4 年且常缺漏,
不足以穩定算 3~5 年 EPS 成長。這裡接兩個更可靠的來源,皆可優雅失敗 (回 None),
讓工具在只有 yfinance 時照常運作:

  - EDGAR companyfacts  : 官方、免費、不需 key。美股歷史 EPS (trailing PEG 用)。
  - FMP analyst-estimates: 需免費 API key (BYOK)。未來 EPS 預估 (forward PEG 用)。

設計: 每個 fetch 函式回 (資料, 說明字串),絕不 raise;呼叫端據此 fallback。
"""

from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
from datetime import date

from . import peg_params as PP


# SEC 要求每個請求帶 User-Agent (含聯絡 email),否則 403。
# 可用環境變數 SEC_EDGAR_USER_AGENT 覆寫 (建議填你自己的 email)。
_DEFAULT_UA = os.environ.get(
    "SEC_EDGAR_USER_AGENT",
    "stock-scenario-valuation (contact: set SEC_EDGAR_USER_AGENT env)",
)


def _http_get_json(url: str, headers: dict | None = None, timeout: int = 15):
    """GET 一個 JSON,失敗回 None (不 raise)。"""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, ValueError, OSError):
        return None


def robust_eps_cagr(series: list[float]) -> float | None:
    """
    穩健 EPS 成長率 = 逐年 YoY 成長率的中位數 (series 為舊→新)。
    對單一離群年份 (一次性項目 / 庫藏股) 不敏感,優於頭尾 CAGR。
    需至少 GROWTH_WINDOW_MIN 年資料 (= 至少 2 個相鄰正值對) 才回值。
    """
    s = [x for x in series if x is not None]
    s = s[-PP.GROWTH_WINDOW_YEARS:]            # 只取近 N 年窗口
    yoy = []
    for prev, cur in zip(s, s[1:]):
        if prev and prev > 0 and cur and cur > 0:
            yoy.append(cur / prev - 1)
    if len(yoy) < (PP.GROWTH_WINDOW_MIN - 1):
        return None
    yoy.sort()
    n = len(yoy)
    mid = n // 2
    return yoy[mid] if n % 2 else (yoy[mid - 1] + yoy[mid]) / 2


# ============================================================
# EDGAR: 歷史 EPS (trailing PEG)
# ============================================================

_CIK_CACHE: dict[str, str] | None = None


def _load_cik_map() -> dict[str, str] | None:
    """載入 ticker → 10 碼 CIK 對照 (SEC 官方清單),快取於記憶體。"""
    global _CIK_CACHE
    if _CIK_CACHE is not None:
        return _CIK_CACHE
    data = _http_get_json(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": _DEFAULT_UA},
    )
    if not data:
        return None
    m = {}
    for row in data.values():
        t = str(row.get("ticker", "")).upper()
        cik = row.get("cik_str")
        if t and cik is not None:
            m[t] = str(int(cik)).zfill(10)
    _CIK_CACHE = m
    return m


def fetch_eps_history_edgar(ticker: str) -> tuple[list[float] | None, str]:
    """
    從 EDGAR companyfacts 抓年度稀釋 EPS 序列 (舊→新)。
    僅美股 10-K 申報者;ADR/外國發行人 (20-F) 覆蓋零散時回 None。

    Returns:
        (eps_series 舊→新, 說明)
    """
    cik_map = _load_cik_map()
    if not cik_map:
        return None, "EDGAR ticker->CIK map fetch failed"
    cik = cik_map.get(ticker.upper())
    if not cik:
        return None, f"EDGAR: {ticker} not found (may not be a US 10-K filer)"

    facts = _http_get_json(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        headers={"User-Agent": _DEFAULT_UA},
    )
    if not facts:
        return None, f"EDGAR companyfacts fetch failed (CIK {cik})"

    all_facts = facts.get("facts", {})
    # 涵蓋兩種申報體系:
    #   - us-gaap (美國國內公司, 10-K)
    #   - ifrs-full (外國發行人 / ADR, 20-F / 40-F, 用 IFRS 科目)
    # 只用「稀釋優先,否則基本」EPS。
    # 註: 這裡抓到的 EPS 只拿來算「成長率」(robust_eps_cagr 的逐年比值),
    #     成長率對幣別與 ADR 比例都是不變量,所以 TWD/每股普通股 也 OK;
    #     trailing PEG 的「水準」(PE) 在 peg.py 用 yfinance 的 USD/每 ADR EPS。
    candidates = [
        ("us-gaap", "EarningsPerShareDiluted"),
        ("us-gaap", "EarningsPerShareBasic"),
        ("ifrs-full", "DilutedEarningsLossPerShare"),
        ("ifrs-full", "BasicEarningsLossPerShare"),
    ]
    ACCEPTED_FORMS = ("10-K", "20-F", "40-F")   # 40-F = 加拿大發行人
    for ns, concept in candidates:
        node = all_facts.get(ns, {}).get(concept)
        if not node:
            continue
        units = node.get("units", {})
        # 優先 USD/shares;否則取任一單位 (只用於成長率,幣別不影響)
        rows = units.get("USD/shares") or next(iter(units.values()), [])
        # 只取年度 (10-K/20-F/40-F, 全年 FY),以財年 fy 去重取最新申報值
        by_fy: dict[int, dict] = {}
        for r in rows:
            if r.get("form") not in ACCEPTED_FORMS or r.get("fp") != "FY":
                continue
            fy = r.get("fy")
            if fy is None or r.get("val") is None:
                continue
            # 同一 fy 可能多次申報 (重述),保留 end 日期最新者
            prev = by_fy.get(fy)
            if prev is None or (r.get("end", "") > prev.get("end", "")):
                by_fy[fy] = r
        if len(by_fy) >= PP.GROWTH_WINDOW_MIN:
            series = [by_fy[fy]["val"] for fy in sorted(by_fy)]
            n = min(len(series), PP.GROWTH_WINDOW_YEARS)
            return series[-PP.GROWTH_WINDOW_YEARS:], f"EDGAR {ns}:{concept}, last {n} yrs"
    return None, "EDGAR: insufficient annual EPS data"


# ============================================================
# FMP: 未來 EPS 預估 (forward PEG)
# ============================================================

def fetch_forward_eps_fmp(ticker: str, api_key: str | None = None
                          ) -> tuple[dict | None, str]:
    """
    從 FMP analyst-estimates 抓未來年度 EPS 共識預估。
    api_key 預設讀環境變數 FMP_API_KEY (BYOK)。

    Returns:
        (dict 或 None, 說明)
        dict = {"forward_eps": 次年預估EPS, "eps_series": [未來逐年EPS 由近到遠],
                "growth": 由近到遠推得的 EPS CAGR, "n_years": 年數}
    """
    key = api_key or os.environ.get("FMP_API_KEY")
    if not key:
        return None, "FMP_API_KEY not set; skipping forward PEG (trailing only)"

    # Stable API (the legacy /api/v3/analyst-estimates was retired 2025-08-31).
    url = (f"https://financialmodelingprep.com/stable/analyst-estimates"
           f"?symbol={ticker.upper()}&period=annual&page=0&limit=10&apikey={key}")
    data = _http_get_json(url)
    if not data or not isinstance(data, list):
        return None, "FMP analyst-estimates fetch failed or empty (check key / plan / quota)"

    today = date.today().isoformat()
    fut = []
    for row in data:
        # stable API renamed the field to epsAvg; keep legacy fallbacks just in case
        eps = (row.get("epsAvg")
               if row.get("epsAvg") is not None else row.get("estimatedEpsAvg"))
        d = str(row.get("date") or row.get("fiscalYear") or "")
        if d and eps is not None and d >= today:
            fut.append((d, float(eps)))
    fut.sort(key=lambda x: x[0])
    fut = fut[:PP.GROWTH_WINDOW_YEARS]
    if len(fut) < PP.GROWTH_WINDOW_MIN:
        return None, "FMP forward-year estimates fewer than 3 years"

    series = [e for _, e in fut]
    forward_eps = series[0]
    # 未來成長: 由第 1 年到第 N 年的 CAGR (需皆為正)
    growth = None
    if series[0] > 0 and series[-1] > 0 and len(series) >= 2:
        growth = (series[-1] / series[0]) ** (1 / (len(series) - 1)) - 1
    return ({"forward_eps": forward_eps, "eps_series": series,
             "growth": growth, "n_years": len(series)},
            f"FMP forward {len(series)}-yr EPS consensus estimates")
