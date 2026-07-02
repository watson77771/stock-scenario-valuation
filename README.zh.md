# stock-scenario-valuation

> 🌐 **語言 / Language**: [English](README.md) ・ **中文（本頁）**

> 輸入任意美股代號，自動抓取財報資料，套用產業分類倍數，產出 **Bear / Base / Bull 三情境**目標價與 Excel 報告。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**作者**：Watson Tsai

> 註：程式的終端與 Excel 輸出為**英文**；本文件為中文說明。

---

## ⚠️ 目前版本說明（請先讀這段）

本工具目前提供**三種互補的估值方法**，可交叉驗證：

| 方法 | 指令 | 看的是 | 適用 | 階段 |
|---|---|---|---|---|
| **三法交叉比較** | **（預設）** | 並排三法，差距即「基本面 vs 成長溢價 vs 市場情緒」訊號 | — | 階段二 ✅ |
| **P/E 本益比法** | `--method pe` | 市場願意給幾倍（靠別人的情緒） | 全部 | 階段一 ✅ |
| **DCF 現金流折現法** | `--method dcf` | 公司一輩子生多少現金折回今天（靠公司本身） | 偏金牛/穩定股 | 階段二 ✅ |
| **PEG 成長校正法** | `--method peg` | 市場為「成長」付的溢價合不合理 | 僅正成長獲利股 | 階段二 ✅ |

**三法各有適用區，這是刻意的分工**：DCF 是保守的基本面下限（金牛股 ≈ 市價、成長股 < 市價）；PEG 補上 DCF 看不到的成長溢價（成長股的主力）；P/E 法兩邊都接。對同一檔股票，三法差異本身就是訊號。

**關於 P/E 法的限制**：它的倍數來自「產業分類固定倍數表」，同一產業所有公司套用**同一組** Bear / Base / Bull 本益比（例如所有半導體股都用 18 / 28 / 40x），不讀取個別公司的新聞、催化劑、護城河。因此對「產業中的特殊公司」可能失準（例如 Apple 的品牌溢價會被當成普通消費電子股而低估）。**這是設計上的取捨，不是 bug** —— 換來的是免費、瞬間、透明、可手動調整（編輯 [`valuate/sector_map.py`](valuate/sector_map.py)）。

**DCF 法則從公司本身的自由現金流出發**，補上 P/E 法看不到的基本面視角。兩種方法結果差異大時，往往是市場定價與基本面出現分歧的訊號。⚠️ DCF 對「基準 FCF」極度敏感，且 yfinance 免費財報常含一次性項目，工具會自動警示，但仍建議手動檢視財報後再下判斷。

**PEG 成長校正法**用「成長率」去解釋本益比合不合理，補上 DCF 對成長股系統性偏低的盲點。它需要可靠的多年 EPS：歷史（trailing）用 **SEC EDGAR**（官方免費、不需 key），未來（forward）用 **FMP 分析師預估**。

> 📌 **要用 forward PEG，需先到 [financialmodelingprep.com](https://site.financialmodelingprep.com/) 免費註冊**（只要 email，免信用卡），登入後儀表板會直接給你 API key，設成環境變數 `FMP_API_KEY` 即可。**沒設 key 時 forward PEG 會自動略過，但 trailing PEG 仍正常運作** —— 不是完全沒有 PEG。

⚠️ PEG 只對正成長、獲利穩定的成長股有意義，對零/負成長、景氣循環、金融、虧損股工具會自動 gating 標警示。

📍 **未來規劃（階段三）**：接入 LLM（Claude API），讓使用者可根據個別公司的即時狀況動態生成更精準的假設。詳見下方[路線圖](#路線圖)。

---

## 這是什麼

大多數估值工具只給你一個目標價。但真實投資決策需要的是**情境思考**：最壞會怎樣（Bear）、合理預期是什麼（Base）、最好能到哪（Bull）。

這個工具讓你輸入一個股票代號，就自動：

1. 從 yfinance 抓取現價、Forward EPS、產業分類
2. 根據產業套用固定的三情境本益比範圍（來自內建對照表，非個別公司客製）
3. 計算 Bear / Base / Bull 目標價與隱含報酬率
4. 與分析師共識目標價對照
5. 輸出終端表格或 Excel 報告

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

## 安裝

```bash
git clone https://github.com/watson77771/stock-scenario-valuation.git
cd stock-scenario-valuation
pip install -r requirements.txt
```

需求：Python 3.10+

---

## 使用方式

```bash
# 預設:三法 (P/E + DCF + PEG) 並排交叉比較 —— 一個指令看完
python -m valuate AAPL

# 只看單一方法的「完整明細」(進階,需要細節時才用)
python -m valuate AAPL --method pe      # 只 P/E
python -m valuate AAPL --method dcf     # 只 DCF (含 WACC 拆解 + 敏感度表)
python -m valuate AAPL --method peg     # 只 PEG (trailing + forward 明細)

# 同時產出 Excel 報告
python -m valuate AAPL --excel
python -m valuate AAPL --method dcf --excel

# 一次估值多家公司
python -m valuate NVDA TSLA AAPL --excel

# 指定 Excel 輸出目錄
python -m valuate AVGO --excel --output-dir ./reports

# 列出所有支援的產業分類
python -m valuate --list-sectors
```

> **三法互為交叉驗證**：P/E 法看「市場願意給幾倍」、DCF 法看「公司本身生多少現金」、
> PEG 法看「市場為成長付的溢價合不合理」。三者差異即訊號。

---

## 運作原理

### 估值方法一：P/E 法

```
目標價 = Forward EPS × 本益比 (P/E)
```

不同情境用不同 P/E：

- **Bear**：市場悲觀 / 風險升溫時的低位倍數
- **Base**：產業中性估值
- **Bull**：市場樂觀 / 題材發酵時的高位倍數

### 倍數從哪來？產業分類表

工具內建一張[產業 → 三情境 P/E 對照表](valuate/sector_map.py)，例如：

| 產業 | Bear | Base | Bull |
|---|---|---|---|
| 半導體 | 18x | 28x | 40x |
| 基礎架構軟體 | 22x | 34x | 48x |
| 能源（煉油） | 8x | 12x | 16x |
| 金融（銀行） | 8x | 11x | 14x |

yfinance 回傳公司的 sector / industry，工具自動歸類套用。找不到對應產業時，使用通用預設 12 / 18 / 26x。

**這些倍數是經驗法則，你可以也應該根據自己的判斷調整** —— 直接編輯 `valuate/sector_map.py`。

### 估值方法二：DCF 現金流折現法（階段二）

P/E 法靠市場情緒；DCF 法靠公司本身能生出多少現金。五步驟：

```
1. 取基準自由現金流 FCF (近 N 年中位數正規化,抵銷 capex 高峰/一次性項目)
2. 預測未來 10 年 FCF (兩段式 fade: 成長率由起始值線性衰減至終值成長)
3. 折現率 WACC = (E/V)·Re + (D/V)·Rd·(1−稅率)，Re = Rf + β×ERP (CAPM)
4. 終值雙軌: Gordon 永續 × 50% + 出場 EV/FCF 倍數 × 50% (加權平均)
5. 折現加總 = 企業價值 EV → 減淨負債 → ÷ 股數 = 每股目標價
```

> **為何不是「5 年 + 純 Gordon」？** 5 年明確期會把高成長公司的成長期過早截斷成永續
> 低成長，且純 Gordon 在 WACC~10% 時隱含終值倍數僅約 13x（市場給優質企業 25–40x），
> 兩者疊加會讓 DCF 對幾乎所有股票都嚴重低於市價。改用 **10 年 fade + 終值雙軌**
> （永續成長與出場倍數各半）後，金牛股 DCF 約貼合市價、成長股 DCF 合理低於市價
> （差距=市場給的成長溢價，由 P/E 法接住）。可用 `python backtest_valuation.py` 自行回測校準。

**參數分三層，只有「營運層」隨情境變**（避免重複計入風險，這是讓三情境有意義的關鍵紀律）：

| 層級 | 參數 | 隨 Bear/Base/Bull 變？ | 來源 |
|---|---|---|---|
| 總經 / 房屋觀點 | 無風險利率 Rf、股權風險溢酬 ERP、終值成長 g_終 | ❌ 三情境固定 | Rf 抓 10Y 美債 `^TNX`；ERP=4.5% (校準至當前 implied ERP) |
| 公司結構 | 稅率、資本結構、債務成本 Rd | ❌ 算一次固定 | yfinance 財報 + 後備值 |
| **公司營運** | **起始成長率 g、出場 EV/FCF 倍數** | ✅ **隨情境變** | 歷史 FCF 穩健成長(中位數 YoY)為 Base 錨，上下展開 |

所有房屋假設集中在 [`valuate/dcf_params.py`](valuate/dcf_params.py)，可依自身觀點調整。

**內建護欄**（DCF 最容易自欺的地方，工具會自動警示）：

- 終值成長 g_終 強制 < WACC（否則 Gordon 那一軌發散）
- 終值佔企業價值 > 80% → 警告「此 DCF 實質在猜終值」
- WACC 落在 6%–12% 外 → 警告參數可能失真
- 正規化基準 FCF 與最新年度差異 > 25% → 警告近期可能含 capex 高峰/一次性項目
- FCF 歷史波動過大 → 警告可能含一次性項目（已自動採中位數正規化緩衝）
- 報告附 **WACC × 終值成長敏感度表**，讓你看見估值對假設有多脆

> ⚠️ **資料品質提醒**：DCF 對「基準 FCF」極度敏感，而 yfinance 的免費財報常含一次性項目或缺漏。
> 遇到工具警示時，請務必手動檢視該公司財報、排除一次性項目後再下判斷。

---

### 估值方法三：PEG 成長校正法（階段二+）

DCF 對成長股系統性偏低（它只折現現金流，看不到市場為「成長」付的溢價）。PEG 法補的正是這塊：用成長率去解釋本益比合不合理。

**產出三樣東西：**

```
1. trailing PEG = (現價 ÷ 歷史 EPS) ÷ 歷史 EPS 成長率   ← EDGAR 歷史，看實績
2. forward  PEG = (現價 ÷ 預估 EPS) ÷ 未來 EPS 成長率   ← FMP 預估，看市場在賭的
3. 成長校正目標價 = (成長率% × 目標 PEG) × EPS          ← Peter Lynch fair value
```

PEG 解讀：**< 1 相對其成長便宜 / 1～2 合理 / > 2 偏貴**。三情境只變「目標 PEG」（市場願意為每單位成長付幾倍）：Bear 1.0 / Base 1.5 / Bull 2.0。

**成長率年期**：歷史與未來都取 **3～5 年**窗口，且用**中位數 YoY**（非頭尾 CAGR）算，避免某一年因庫藏股或一次性項目扭曲。

**資料源（分層、可優雅退場）：**

| 用途 | 來源 | 需 key | 說明 |
|---|---|---|---|
| 歷史 EPS（trailing） | SEC EDGAR `companyfacts` | ❌ 免費 | 官方申報值，最準；美股 10-K 申報者 |
| 未來 EPS（forward） | FMP `analyst-estimates` | ✅ BYOK | 設 `FMP_API_KEY`；無 key 時自動只算 trailing |

```bash
# 設定 FMP key（沒有就只會有 trailing PEG）
export FMP_API_KEY="你的_FMP_免費_key"
# 建議也設 EDGAR User-Agent（SEC 要求帶聯絡 email）
export SEC_EDGAR_USER_AGENT="your-app your-email@example.com"

python -m valuate AAPL --method peg
python -m valuate AAPL --method peg --excel
```

**內建 gating（PEG 最容易自欺的地方，工具自動把關）：**

- EPS ≤ 0（虧損）→ 本益比無意義，不產目標價
- 成長 < 5% → 低成長，PEG 分母過小失真，標「不適用、改用 DCF」
- 成長 > 50% → 超高成長不可持續，標警示並把成長率夾至上限
- 景氣循環 / 金融 / 公用 / 房地產 → EPS 成長代表性低，標「參考性弱」

> ⚠️ PEG 是**成長股專用**的交叉驗證，不是萬用估值。金牛股看 DCF、成長股看 PEG、P/E 法兩邊都接 —— 三法分工才是這個設計的價值。

---

## 路線圖

| 階段 | 狀態 | 內容 |
|---|---|---|
| **階段一** | ✅ 完成 | 產業分類表 P/E 估值 / CLI / Excel 輸出 |
| **階段二** | ✅ 完成 | FCF 現金流折現法 / PEG 成長校正法（三法交叉驗證 + 雙語文件） |
| **階段三** | 🔮 研究中 | SOTP 業務分拆法 / 批次 portfolio 估值 / LLM 動態假設生成（Claude API） |

### 關於階段三（LLM 假設生成）

產業分類表是「靜態」的 —— 它不知道某家公司當下有什麼特殊催化劑。階段三會接入 Claude API，根據公司的即時狀況動態生成更精準的三情境假設。

**這是選配功能，採 BYOK（Bring Your Own Key）模式**：

```bash
# 階段三啟用後 (目前為預留接口)
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
python -m valuate TSLA --use-llm
```

- 使用者需自備 [Anthropic API key](https://console.anthropic.com)
- 成本約每次估值 $0.01–0.05，直接付給 Anthropic（作者不經手任何費用）
- 沒有 API key 時，工具自動 fallback 回產業分類表（免費版照常運作）

---

## 專案結構

```
stock-scenario-valuation/
├── valuate/
│   ├── cli.py                  # 命令列入口 (--method pe/dcf/peg/both)
│   ├── fetcher.py              # yfinance 資料抓取 (含 DCF 財報 + Rf)
│   ├── sector_map.py           # 產業 → P/E 對照表 (核心 know-how)
│   ├── engine.py               # P/E 法估值引擎 (階段一)
│   ├── dcf.py                  # DCF 法估值引擎 (階段二)
│   ├── wacc.py                 # WACC 計算 + 護欄 (階段二)
│   ├── dcf_params.py           # DCF 房屋假設 (ERP/g_終/出場倍數/護欄)
│   ├── peg.py                  # PEG 成長校正估值引擎 (階段二+)
│   ├── peg_params.py           # PEG 房屋假設 (目標PEG/gating 門檻)
│   ├── datasources.py          # EDGAR 歷史 EPS + FMP 預估 EPS 資料源
│   ├── output.py               # 終端 / Excel 輸出 (P/E + DCF + PEG)
│   └── assumptions/
│       ├── base.py             # 假設引擎抽象介面
│       ├── sector_based.py     # 階段一：產業分類
│       └── llm_based.py        # 階段三：LLM (預留)
├── examples/
├── tests/
├── backtest_valuation.py       # DCF 校準回測 (金牛股 vs 成長股)
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 免責聲明

本工具產出的所有估值為**情境分析與教育用途，不構成投資建議**。

- 產業倍數為經驗法則，可能不適用於特定公司或市場狀況
- yfinance 資料可能延遲或不準確
- 虧損公司（EPS ≤ 0）的 P/E 法不適用，結果僅供參考
- 投資決策請自行研究並諮詢專業意見

作者不對任何依本工具做出的投資決策負責。

---

## 授權

[MIT License](LICENSE) © Watson Tsai
