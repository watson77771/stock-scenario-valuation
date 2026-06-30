# stock-scenario-valuation

> 🌐 **Language / 語言**: **English (this page)** ・ [中文](README.zh.md)

> Enter any US ticker, auto-fetch financials, apply sector multiples, and produce **Bear / Base / Bull** three-scenario target prices and an Excel report.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Author**: Watson Tsai

---

## ⚠️ Current version (read this first)

The tool ships **three complementary valuation methods** that cross-check each other:

| Method | Command | What it sees | Best for | Stage |
|---|---|---|---|---|
| **P/E multiple** | (default) | what multiple the market will pay (others' sentiment) | all | Stage 1 ✅ |
| **DCF (discounted cash flow)** | `--method dcf` | how much cash the company itself generates, discounted to today | cash cows / stable names | Stage 2 ✅ |
| **PEG (growth-adjusted)** | `--method peg` | whether the premium paid for "growth" is reasonable | profitable, positive-growth only | Stage 2+ ✅ |
| **Three-way cross-check** | `--method both` | all three side by side; the spread is the signal | — | Stage 2+ ✅ |

**Each method has its own zone — that division of labor is deliberate.** DCF is a conservative fundamentals floor (cash cows ≈ price, growth names < price); PEG captures the growth premium DCF can't see (mainly for growth names); P/E catches both sides. For a given stock, the spread between the three is itself a signal.

**On the P/E method's limit**: its multiples come from a fixed sector-classification table. Every company in a sector uses the **same** Bear / Base / Bull P/E (e.g. all semiconductors use 18 / 28 / 40x), ignoring company-specific news, catalysts and moat. So it can misprice "special companies within a sector" (e.g. Apple's brand premium gets treated like a generic consumer-electronics name and undervalued). **This is a design trade-off, not a bug** — in exchange you get free, instant, transparent, hand-tunable output (edit [`valuate/sector_map.py`](valuate/sector_map.py)).

**DCF starts from the company's own free cash flow**, adding the fundamentals view the P/E method can't see. When the two methods diverge a lot, that's often a sign the market price and fundamentals disagree. ⚠️ DCF is extremely sensitive to "base FCF", and yfinance's free financials often contain one-off items; the tool warns automatically, but manual review of the statements is still advised.

**The PEG method** uses the growth rate to judge whether a P/E is reasonable, covering DCF's blind spot of systematically undervaluing growth names. It needs reliable multi-year EPS: history from **SEC EDGAR** (official, free), the future from **FMP analyst estimates** (bring your own free API key via env var `FMP_API_KEY`; without a key it computes trailing PEG only). ⚠️ PEG is only meaningful for profitable, positive-growth names; for zero/negative-growth, cyclical, financial and loss-making stocks the tool automatically gates and flags it.

📍 **Roadmap (stage 3)**: integrate an LLM (Claude API) so users can generate sharper, company-specific assumptions from each company's live situation. See the [roadmap](#roadmap) below.

---

## What this is

Most valuation tools give you a single target price. But real investment decisions need **scenario thinking**: how bad is the worst case (Bear), what's a fair expectation (Base), how high could it go (Bull).

Enter one ticker and the tool automatically:

1. Fetches price, forward EPS and sector from yfinance
2. Applies a fixed three-scenario P/E range by sector (from a built-in table, not company-specific)
3. Computes Bear / Base / Bull targets and implied returns
4. Compares against the analyst consensus target
5. Prints a terminal table or writes an Excel report

```
$ python -m valuate AVGO

================================================================
  AVGO  Broadcom Inc
================================================================
  Sector     : Technology / Semiconductors
  Price      : $433.62
  EPS (forward): $13.50
  Source     : sector_table [industry: Semiconductors]

  Scenario       P/E        Target      Return
  --------------------------------------------
  Bear         18.0x     $243.00      -44.0%
  Base         28.0x     $378.00      -12.8%
  Bull         40.0x     $540.00      +24.5%

  Analyst avg: $458.00 (ref)
  Rationale  : Per sector-classification table (industry: Semiconductors). AI tailwind / cyclical / leaders command a premium
```

---

## Install

```bash
git clone https://github.com/watson77771/stock-scenario-valuation.git
cd stock-scenario-valuation
pip install -r requirements.txt
```

Requires Python 3.10+

---

## Usage

```bash
# Value a single company (terminal output, default P/E method)
python -m valuate AVGO

# DCF (discounted cash flow) method (stage 2)
python -m valuate AAPL --method dcf

# PEG growth-adjusted method (EDGAR history + FMP estimates)
python -m valuate AAPL --method peg

# All three methods side by side
python -m valuate AAPL --method both

# Also write an Excel report
python -m valuate AVGO --excel
python -m valuate AAPL --method dcf --excel

# Value several companies at once
python -m valuate NVDA TSLA AAPL --excel

# Choose the Excel output directory
python -m valuate AVGO --excel --output-dir ./reports

# List all supported sector classifications
python -m valuate --list-sectors
```

> **The three methods cross-validate each other**: P/E sees "what multiple the market will pay",
> DCF sees "how much cash the company itself generates", PEG sees "whether the premium paid for
> growth is reasonable". A large divergence is itself the signal.

---

## How it works

### Method 1: P/E

```
Target = Forward EPS × P/E
```

Each scenario uses a different P/E:

- **Bear**: a low multiple when the market is pessimistic / risk is rising
- **Base**: a neutral sector valuation
- **Bull**: a high multiple when the market is optimistic / a theme is in play

### Where do the multiples come from? The sector table

The tool ships a [sector -> three-scenario P/E table](valuate/sector_map.py), e.g.:

| Sector | Bear | Base | Bull |
|---|---|---|---|
| Semiconductors | 18x | 28x | 40x |
| Infrastructure software | 22x | 34x | 48x |
| Energy (refining) | 8x | 12x | 16x |
| Financials (banks) | 8x | 11x | 14x |

yfinance returns the company's sector / industry and the tool classifies automatically. When no sector matches, it falls back to a generic default of 12 / 18 / 26x.

**These multiples are rules of thumb; you can and should adjust them to your own judgment** — just edit `valuate/sector_map.py`.

### Method 2: DCF (discounted cash flow) (stage 2)

P/E rides market sentiment; DCF rides how much cash the company itself can produce. Five steps:

```
1. Take base free cash flow (FCF), median-normalized over the last N years to offset capex peaks / one-offs
2. Project the next 10 years of FCF (two-stage fade: growth declines linearly from the starting rate to terminal growth)
3. Discount rate WACC = (E/V)·Re + (D/V)·Rd·(1-tax), Re = Rf + beta×ERP (CAPM)
4. Dual-track terminal: Gordon perpetuity × 50% + exit EV/FCF multiple × 50% (weighted average)
5. Sum of PVs = enterprise value EV -> subtract net debt -> / shares = target per share
```

> **Why not "5 years + pure Gordon"?** A 5-year explicit window truncates a growth company's
> growth period too early into low perpetuity growth, and at WACC ~10% pure Gordon implies a
> terminal multiple of only ~13x (the market pays quality businesses 25-40x). Together those make
> DCF land far below market for almost every stock. With **10-year fade + dual-track terminal**
> (perpetuity growth and exit multiple, half each), cash cows roughly match price while growth
> names sit reasonably below it (the gap = the market's priced-in growth premium, which the P/E
> method catches). Run `python backtest_valuation.py` to backtest the calibration yourself.

**Parameters are split into three layers; only the operating layer varies by scenario** (avoiding double-counting risk — the discipline that makes three scenarios meaningful):

| Layer | Parameters | Varies with Bear/Base/Bull? | Source |
|---|---|---|---|
| Macro / house view | risk-free rate Rf, equity risk premium ERP, terminal growth g_inf | ❌ fixed across scenarios | Rf from 10Y UST `^TNX`; ERP=4.5% (calibrated to current implied ERP) |
| Company structure | tax rate, capital structure, cost of debt Rd | ❌ computed once | yfinance financials + fallbacks |
| **Company operations** | **starting growth g, exit EV/FCF multiple** | ✅ **varies by scenario** | historical robust FCF growth (median YoY) as Base anchor, spread up/down |

All house assumptions live in [`valuate/dcf_params.py`](valuate/dcf_params.py), adjustable to your own view.

**Built-in guardrails** (where DCF most easily fools itself — the tool warns automatically):

- Terminal growth g_inf forced < WACC (else the Gordon track diverges)
- Terminal value > 80% of EV -> warns "this DCF is essentially guessing the terminal value"
- WACC outside 6%-12% -> warns the inputs may be distorted
- Normalized base FCF differs from the latest year by > 25% -> warns of a likely recent capex peak / one-off
- Highly volatile FCF history -> warns of possible one-off items (already median-normalized as a buffer)
- The report includes a **WACC × terminal-growth sensitivity table** so you can see how fragile the valuation is to assumptions

> ⚠️ **Data-quality note**: DCF is extremely sensitive to "base FCF", and yfinance's free financials
> often contain one-off items or gaps. When the tool warns, review the company's statements and
> strip one-off items before drawing conclusions.

---

### Method 3: PEG (growth-adjusted) (stage 2+)

DCF systematically undervalues growth names (it only discounts cash flow and can't see the premium the market pays for "growth"). PEG fills exactly that gap: it uses the growth rate to judge whether a P/E is reasonable.

**It produces three things:**

```
1. trailing PEG = (price / historical EPS) / historical EPS growth   <- EDGAR history, the track record
2. forward  PEG = (price / estimated EPS) / future EPS growth        <- FMP estimates, what the market is betting
3. growth-adjusted target = (growth% × target PEG) × EPS             <- Peter Lynch fair value
```

PEG read: **< 1 cheap relative to its growth / 1-2 fair / > 2 pricey**. The three scenarios only vary the "target PEG" (how many P/E points the market pays per unit of growth): Bear 1.0 / Base 1.5 / Bull 2.0.

**Growth window**: both history and the future use a **3-5 year** window, computed with the **median YoY** (not endpoint CAGR) to avoid a single year being distorted by buybacks or one-off items.

**Data sources (layered, with graceful fallback):**

| Use | Source | Key needed | Notes |
|---|---|---|---|
| Historical EPS (trailing) | SEC EDGAR `companyfacts` | ❌ free | official filed values, most accurate; US 10-K filers |
| Future EPS (forward) | FMP `analyst-estimates` | ✅ BYOK | set `FMP_API_KEY`; without a key, trailing only |

```bash
# Set the FMP key (without it you only get trailing PEG)
export FMP_API_KEY="your_free_FMP_key"
# Also set an EDGAR User-Agent (SEC requires a contact email)
export SEC_EDGAR_USER_AGENT="your-app your-email@example.com"

python -m valuate AAPL --method peg
python -m valuate AAPL --method peg --excel
```

**Built-in gating (where PEG most easily fools itself — the tool guards automatically):**

- EPS ≤ 0 (loss-making) -> P/E is meaningless, no target produced
- growth < 5% -> low growth, PEG denominator too small and distorted; flagged "N/A, use DCF"
- growth > 50% -> very high growth is unsustainable; warned and the growth clamped to the cap
- cyclical / financial / utilities / real estate -> EPS growth not representative; flagged "weak reference value"

> ⚠️ PEG is a **growth-stock-specific** cross-check, not a universal valuation. Cash cows -> DCF,
> growth names -> PEG, P/E catches both. That division of labor is the point of this design.

---

## Roadmap

| Stage | Status | Content |
|---|---|---|
| **Stage 1** | ✅ done | sector-table P/E valuation / CLI / Excel output |
| **Stage 2** | 🚧 in progress | **FCF DCF ✅** / **PEG growth-adjusted ✅** / SOTP sum-of-the-parts 🔜 / batch portfolio 🔜 |
| **Stage 3** | 🔮 research | LLM-generated dynamic assumptions (Claude API) |

### About stage 3 (LLM assumption generation)

The sector table is "static" — it doesn't know what special catalyst a company has right now. Stage 3 will integrate the Claude API to dynamically generate sharper three-scenario assumptions from a company's live situation.

**It's optional, and BYOK (Bring Your Own Key):**

```bash
# Once stage 3 is enabled (currently a reserved interface)
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
python -m valuate TSLA --use-llm
```

- You supply your own [Anthropic API key](https://console.anthropic.com)
- Roughly $0.01-0.05 per valuation, paid directly to Anthropic (the author never handles any fees)
- Without an API key the tool falls back to the sector table (the free version works as usual)

---

## Project structure

```
stock-scenario-valuation/
├── valuate/
│   ├── cli.py                  # CLI entry point (--method pe/dcf/peg/both)
│   ├── fetcher.py              # yfinance data fetch (incl. DCF financials + Rf)
│   ├── sector_map.py           # sector -> P/E table (core know-how)
│   ├── engine.py               # P/E valuation engine (stage 1)
│   ├── dcf.py                  # DCF valuation engine (stage 2)
│   ├── wacc.py                 # WACC computation + guardrails (stage 2)
│   ├── dcf_params.py           # DCF house assumptions (ERP/g_inf/exit multiple/guardrails)
│   ├── peg.py                  # PEG growth-adjusted engine (stage 2+)
│   ├── peg_params.py           # PEG house assumptions (target PEG / gating thresholds)
│   ├── datasources.py          # EDGAR historical EPS + FMP estimated EPS sources
│   ├── output.py               # terminal / Excel output (P/E + DCF + PEG)
│   └── assumptions/
│       ├── base.py             # assumption-engine abstract interface
│       ├── sector_based.py     # stage 1: sector classification
│       └── llm_based.py        # stage 3: LLM (reserved)
├── examples/
├── tests/
├── backtest_valuation.py       # DCF calibration backtest (cash cows vs growth)
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Disclaimer

All valuations produced by this tool are **scenario analysis for educational purposes and do not constitute investment advice**.

- Sector multiples are rules of thumb and may not fit a specific company or market regime
- yfinance data may be delayed or inaccurate
- The P/E method does not apply to loss-making companies (EPS ≤ 0); results are for reference only
- Do your own research and consult a professional before making investment decisions

The author is not responsible for any investment decision made based on this tool.

---

## License

[MIT License](LICENSE) © Watson Tsai
