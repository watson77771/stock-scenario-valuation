"""
cli.py
======
命令列入口。

用法:
  python -m valuate AVGO                  # 終端輸出 (產業分類表假設)
  python -m valuate AVGO --excel          # 同時產出 xlsx
  python -m valuate NVDA TSLA AAPL        # 多家公司
  python -m valuate AVGO --use-llm        # 用 Claude API (階段三,需 API key)
  python -m valuate --list-sectors        # 列出支援的產業
"""

from __future__ import annotations
import argparse
import io
import sys

# Windows 編碼修正
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from .fetcher import fetch_company
from .engine import ValuationEngine
from .assumptions.sector_based import SectorBasedAssumptions
from .assumptions.llm_based import LLMBasedAssumptions
from .output import print_result, write_xlsx
from . import sector_map


def build_engine(use_llm: bool) -> ValuationEngine:
    """根據參數選擇假設引擎"""
    if use_llm:
        assumption_engine = LLMBasedAssumptions(fallback=True)
    else:
        assumption_engine = SectorBasedAssumptions()
    return ValuationEngine(assumption_engine)


def run_one(ticker: str, engine: ValuationEngine, to_excel: bool, output_dir: str):
    """估值單一公司"""
    print(f"\n→ 抓取 {ticker} ...")
    company = fetch_company(ticker)

    if company.fetch_errors:
        for e in company.fetch_errors:
            print(f"  ⚠️  {e}")

    if not company.is_valid:
        print(f"  ❌ {ticker} 資料不足,無法估值 (可能是無效代號或資料源問題)")
        return

    try:
        result = engine.value(company)
    except ValueError as e:
        print(f"  ❌ {e}")
        return

    print_result(result)

    if to_excel:
        path = write_xlsx(result, output_dir)
        print(f"  📄 已輸出: {path}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="valuate",
        description="股票三情境估值工具 (Bear/Base/Bull)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tickers", nargs="*", help="股票代號 (可多個)")
    parser.add_argument("--excel", action="store_true", help="產出 xlsx 報告")
    parser.add_argument("--use-llm", action="store_true",
                        help="用 Claude API 生成假設 (階段三,需 ANTHROPIC_API_KEY)")
    parser.add_argument("--output-dir", default=".", help="xlsx 輸出目錄")
    parser.add_argument("--list-sectors", action="store_true",
                        help="列出所有支援的產業分類")
    args = parser.parse_args()

    if args.list_sectors:
        supported = sector_map.list_supported()
        print("\n支援的細分產業 (industry):")
        for ind in supported["industries"]:
            print(f"  - {ind}")
        print("\n支援的粗分產業 (sector):")
        for sec in supported["sectors"]:
            print(f"  - {sec}")
        print("\n其他產業會 fallback 至通用預設 P/E 12/18/26x\n")
        return

    if not args.tickers:
        parser.print_help()
        return

    engine = build_engine(args.use_llm)

    for ticker in args.tickers:
        run_one(ticker, engine, args.excel, args.output_dir)


if __name__ == "__main__":
    main()
