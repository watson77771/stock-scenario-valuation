"""
backtest_valuation.py
=====================
DCF 校準驗證 — 用一籃子「穩定金牛股」回測 DCF Base 目標價與市價的偏離度。

目的:
  DCF 對「成長股」低於市價是合理訊號 (市場定價超出基本面);但對「穩定金牛股」
  (低成長、市場本來就用現金流定價) 若也嚴重偏離,代表是「模型結構偏差」而非訊號。
  本腳本把兩類股票分開回測,讓你一眼分辨:
    - 金牛股 DCF/市價 接近 1.0  → 模型校準良好
    - 金牛股 DCF/市價 顯著 < 1   → 模型仍系統性偏低 (該檢視終值/WACC)
    - 成長股 DCF/市價 < 1         → 預期內,差距 = 市場對成長的想像溢價

執行:
  python backtest_valuation.py
  python backtest_valuation.py --excel-dir ./reports   # 順便存每檔 xlsx

需網路 (yfinance)。若抓取失敗會略過該檔並於結尾彙總成功率。
"""

from __future__ import annotations
import argparse
import statistics
import sys

from valuate.fetcher import fetch_company, fetch_risk_free_rate
from valuate.dcf import DCFEngine


# 穩定金牛股: 低成長、現金流穩定,市場本來就接近用 DCF 定價 → 校準基準
CASH_COWS = ["KO", "PG", "JNJ", "PEP", "MCD", "CL", "XOM", "CVX"]

# 成長/高品質股: 預期 DCF < 市價 (差距 = 成長溢價,屬合理訊號,非 bug)
GROWTH = ["AAPL", "MSFT", "GOOGL", "NVDA", "V"]


def _ratio_str(dcf_base: float, price: float) -> str:
    r = dcf_base / price if price else 0.0
    flag = "✅" if 0.75 <= r <= 1.3 else ("🔶" if 0.5 <= r < 0.75 else "🔻")
    return f"{r:5.2f}x {flag}"


def run_basket(label: str, tickers: list[str], rf: float, excel_dir: str | None):
    print(f"\n{'=' * 72}\n  {label}\n{'=' * 72}")
    print(f"  {'代號':<8}{'現價':>10}{'DCF Base':>12}{'DCF/市價':>14}"
          f"{'隱含倍數':>10}{'分析師':>10}")
    print("  " + "-" * 66)

    engine = DCFEngine(rf)
    ratios = []
    for tk in tickers:
        try:
            c = fetch_company(tk, fetch_dcf=True)
            if not c.has_dcf_data:
                print(f"  {tk:<8}{'(缺 DCF 資料,略過)':>40}")
                continue
            r = engine.value(c)
            price = r.current_price
            base = r.base.target
            ratios.append(base / price if price else 0.0)
            analyst = f"${c.analyst_target_mean:,.0f}" if c.analyst_target_mean else "—"
            print(f"  {tk:<8}${price:>8,.2f} ${base:>10,.2f}  {_ratio_str(base, price):>12}"
                  f"{r.base.implied_terminal_multiple:>8.0f}x{analyst:>10}")
            if excel_dir:
                from valuate.output import write_dcf_xlsx
                write_dcf_xlsx(r, excel_dir)
        except Exception as e:
            print(f"  {tk:<8}抓取/估值失敗: {e}")

    if ratios:
        med = statistics.median(ratios)
        print("  " + "-" * 66)
        print(f"  中位數 DCF/市價 = {med:.2f}x   "
              f"(樣本 {len(ratios)} 檔;1.0 = 完美貼合市價)")
    return ratios


def main():
    ap = argparse.ArgumentParser(description="DCF 校準回測")
    ap.add_argument("--excel-dir", default=None, help="若指定,順便輸出每檔 xlsx 到此目錄")
    args = ap.parse_args()

    rf, rf_note = fetch_risk_free_rate()
    print(f"ℹ️  {rf_note}")

    cow_r = run_basket("穩定金牛股 (校準基準 — 應接近 1.0x)", CASH_COWS, rf, args.excel_dir)
    grw_r = run_basket("成長/高品質股 (預期 < 1.0x — 差距=成長溢價)", GROWTH, rf, args.excel_dir)

    print(f"\n{'=' * 72}\n  判讀\n{'=' * 72}")
    if cow_r:
        med = statistics.median(cow_r)
        if med >= 0.85:
            print(f"  金牛股中位數 {med:.2f}x → ✅ 模型校準良好,沒有系統性偏低。")
        elif med >= 0.65:
            print(f"  金牛股中位數 {med:.2f}x → 🔶 略偏低,可微調出場倍數或 ERP。")
        else:
            print(f"  金牛股中位數 {med:.2f}x → 🔻 仍系統性偏低,建議再檢視終值雙軌權重 / WACC。")
    if grw_r:
        print(f"  成長股中位數 {statistics.median(grw_r):.2f}x → 低於 1 屬正常 "
              f"(市場對未來成長的想像,P/E 法會接住這塊)。")
    print()


if __name__ == "__main__":
    sys.exit(main())
