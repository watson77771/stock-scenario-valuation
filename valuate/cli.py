"""
cli.py
======
Command-line entry point.

Usage:
  python -m valuate AVGO                  # P/E method (sector-table assumptions)
  python -m valuate AVGO --excel          # also write xlsx
  python -m valuate NVDA TSLA AAPL        # multiple companies
  python -m valuate AAPL --method dcf     # DCF (discounted cash flow)
  python -m valuate AAPL --method dcf --excel
  python -m valuate AAPL --method peg     # growth-adjusted (EDGAR history + FMP estimates)
  python -m valuate AAPL --method both    # P/E, DCF, PEG side-by-side cross-check
  python -m valuate AVGO --use-llm        # Claude API assumptions (stage 3, needs API key)
  python -m valuate --list-sectors        # list supported sectors
"""

from __future__ import annotations
import argparse
import io
import sys

# Windows encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from .fetcher import fetch_company, fetch_risk_free_rate
from .engine import ValuationEngine
from .dcf import DCFEngine
from .peg import PEGEngine
from .datasources import fetch_eps_history_edgar, fetch_forward_eps_fmp
from .assumptions.sector_based import SectorBasedAssumptions
from .assumptions.llm_based import LLMBasedAssumptions
from .output import (print_result, write_xlsx, print_dcf_result,
                     write_dcf_xlsx, print_comparison, print_peg_result,
                     write_peg_xlsx)
from . import sector_map


def _run_peg(company):
    """Fetch EDGAR historical EPS + FMP forward EPS, run the PEG engine."""
    eps_hist, eps_note = fetch_eps_history_edgar(company.ticker)
    print(f"  i  {eps_note}")
    fwd, fwd_note = fetch_forward_eps_fmp(company.ticker)
    print(f"  i  {fwd_note}")
    return PEGEngine().value(company, eps_history=eps_hist, fwd_estimates=fwd)


def build_engine(use_llm: bool) -> ValuationEngine:
    """Pick the assumption engine based on flags."""
    if use_llm:
        assumption_engine = LLMBasedAssumptions(fallback=True)
    else:
        assumption_engine = SectorBasedAssumptions()
    return ValuationEngine(assumption_engine)


def run_one(ticker: str, engine, to_excel: bool, output_dir: str,
            method: str = "pe", dcf_engine=None):
    """Value a single company (method = 'pe' / 'dcf' / 'peg' / 'both')."""
    print(f"\n-> Fetching {ticker} ...")
    company = fetch_company(ticker, fetch_dcf=(method in ("dcf", "both")))

    if company.fetch_errors:
        for e in company.fetch_errors:
            print(f"  !  {e}")

    if method == "both":
        pe_res = dcf_res = peg_res = None
        if company.is_valid:
            try:
                pe_res = engine.value(company)
            except ValueError:
                pass
        if company.has_dcf_data:
            try:
                dcf_res = dcf_engine.value(company)
            except ValueError:
                pass
        if company.is_valid:
            try:
                peg_res = _run_peg(company)
            except Exception as e:
                print(f"  !  PEG skipped: {e}")
        if pe_res is None and dcf_res is None and peg_res is None:
            print(f"  X  {ticker}: all three methods failed to value")
            return
        print_comparison(pe_res, dcf_res, peg_res)
        if to_excel:
            if pe_res:
                print(f"  Saved: {write_xlsx(pe_res, output_dir)}")
            if dcf_res:
                print(f"  Saved: {write_dcf_xlsx(dcf_res, output_dir)}")
            if peg_res:
                print(f"  Saved: {write_peg_xlsx(peg_res, output_dir)}")
            print()
        return

    if method == "peg":
        if not company.is_valid:
            print(f"  X  {ticker}: insufficient data (missing price/EPS), can't run PEG")
            return
        result = _run_peg(company)
        print_peg_result(result)
        if to_excel:
            print(f"  Saved: {write_peg_xlsx(result, output_dir)}\n")
        return

    if method == "dcf":
        if not company.has_dcf_data:
            print(f"  X  {ticker}: missing required DCF data (FCF/shares/price), "
                  f"can't run DCF (try the default P/E method)")
            return
        try:
            result = engine.value(company)
        except ValueError as e:
            print(f"  X  {e}")
            return
        print_dcf_result(result)
        if to_excel:
            path = write_dcf_xlsx(result, output_dir)
            print(f"  Saved: {path}\n")
        return

    # --- default P/E method ---
    if not company.is_valid:
        print(f"  X  {ticker}: insufficient data to value (invalid ticker or data-source issue)")
        return

    try:
        result = engine.value(company)
    except ValueError as e:
        print(f"  X  {e}")
        return

    print_result(result)

    if to_excel:
        path = write_xlsx(result, output_dir)
        print(f"  Saved: {path}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="valuate",
        description="Three-scenario stock valuation tool (Bear/Base/Bull)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tickers", nargs="*", help="ticker symbols (one or more)")
    parser.add_argument("--method", choices=["pe", "dcf", "peg", "both"], default="pe",
                        help="valuation method: pe=P/E (default) / dcf=discounted cash flow / "
                             "peg=growth-adjusted (EDGAR history + FMP estimates) / "
                             "both=all three side-by-side")
    parser.add_argument("--excel", action="store_true", help="write an xlsx report")
    parser.add_argument("--use-llm", action="store_true",
                        help="use Claude API for assumptions (stage 3, needs ANTHROPIC_API_KEY; P/E only)")
    parser.add_argument("--output-dir", default=".", help="xlsx output directory")
    parser.add_argument("--list-sectors", action="store_true",
                        help="list all supported sector classifications")
    args = parser.parse_args()

    if args.list_sectors:
        supported = sector_map.list_supported()
        print("\nSupported industries (fine):")
        for ind in supported["industries"]:
            print(f"  - {ind}")
        print("\nSupported sectors (coarse):")
        for sec in supported["sectors"]:
            print(f"  - {sec}")
        print("\nOther sectors fall back to the generic default P/E 12/18/26x\n")
        return

    if not args.tickers:
        parser.print_help()
        return

    if args.method in ("dcf", "both"):
        rf, rf_note = fetch_risk_free_rate()
        print(f"  i  {rf_note}")

    dcf_engine = None
    if args.method == "dcf":
        engine = DCFEngine(rf)
    elif args.method == "both":
        engine = build_engine(args.use_llm)
        dcf_engine = DCFEngine(rf)
    else:
        engine = build_engine(args.use_llm)

    for ticker in args.tickers:
        run_one(ticker, engine, args.excel, args.output_dir, args.method, dcf_engine)


if __name__ == "__main__":
    main()
