# stock-scenario-valuation

> 輸入任意美股代號，自動抓取財報資料，套用產業分類倍數，產出 **Bear / Base / Bull 三情境**目標價與 Excel 報告。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**作者**：Watson Tsai

---

## 這是什麼

大多數估值工具只給你一個目標價。但真實投資決策需要的是**情境思考**：最壞會怎樣（Bear）、合理預期是什麼（Base）、最好能到哪（Bull）。

這個工具讓你輸入一個股票代號，就自動：

1. 從 yfinance 抓取現價、Forward EPS、產業分類
2. 根據產業套用合理的三情境本益比範圍
3. 計算 Bear / Base / Bull 目標價與隱含報酬率
4. 與分析師共識目標價對照
5. 輸出終端表格或 Excel 報告

```
$ python -m valuate AVGO

================================================================
  AVGO  Broadcom Inc
================================================================
  產業       : Technology / Semiconductors
  現價       : $433.62
  EPS (forward ): $13.50
  假設來源   : sector_table [industry: Semiconductors]

  情境         P/E         目標價        報酬率
  ------------------------------------------
  Bear       18.0x     $243.00      -44.0%
  Base       28.0x     $378.00      -12.8%
  Bull       40.0x     $540.00      +24.5%

  分析師均價 : $458.00 (參考)
  理由       : 依產業分類對照表 (industry: Semiconductors)。AI 題材推升 / 週期性強 / 龍頭享溢價
```

---

## 安裝

```bash
git clone https://github.com/<your-username>/stock-scenario-valuation.git
cd stock-scenario-valuation
pip install -r requirements.txt
```

需求：Python 3.10+

---

## 使用方式

```bash
# 估值單一公司 (終端輸出,預設 P/E 法)
python -m valuate AVGO

# 用 DCF 現金流折現法估值 (階段二)
python -m valuate AAPL --method dcf

# 同時產出 Excel 報告
python -m valuate AVGO --excel
python -m valuate AAPL --method dcf --excel

# 一次估值多家公司
python -m valuate NVDA TSLA AAPL --excel

# 指定 Excel 輸出目錄
python -m valuate AVGO --excel --output-dir ./reports

# 列出所有支援的產業分類
python -m valuate --list-sectors
```

> **兩種方法互為交叉驗證**：P/E 法看「市場願意給幾倍」(靠別人的情緒)，
> DCF 法看「公司一輩子生多少現金折回今天」(靠公司本身)。
> 兩者差異大時，往往是市場定價與基本面出現分歧的訊號。

---

## 運作原理

### 估值方法：P/E 法

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
| 能源（煉油）| 8x | 12x | 16x |
| 金融（銀行）| 8x | 11x | 14x |

yfinance 回傳公司的 sector / industry，工具自動歸類套用。找不到對應產業時，使用通用預設 12/18/26x。

**這些倍數是經驗法則，你可以也應該根據自己的判斷調整** — 直接編輯 `valuate/sector_map.py`。

### 估值方法二：DCF 現金流折現法（階段二）

P/E 法靠市場情緒；DCF 法靠公司本身能生出多少現金。五步驟：

```
1. 取基準自由現金流 FCF (優先用年度現金流量表最新值)
2. 預測未來 5 年 FCF (依成長率 g)
3. 折現率 WACC = (E/V)·Re + (D/V)·Rd·(1−稅率)，Re = Rf + β×ERP (CAPM)
4. 終值 TV = FCF_5 × (1+g_終) / (WACC − g_終)   ← Gordon 永續成長
5. 折現加總 = 企業價值 EV → 減淨負債 → ÷ 股數 = 每股目標價
```

**參數分三層，只有「營運層」隨情境變**（避免重複計入風險，這是讓三情境有意義的關鍵紀律）：

| 層級 | 參數 | 隨 Bear/Base/Bull 變？ | 來源 |
|---|---|---|---|
| 總經 / 房屋觀點 | 無風險利率 Rf、股權風險溢酬 ERP、終值成長 g_終 | ❌ 三情境固定 | Rf 抓 10Y 美債 `^TNX`；ERP=5.0% (Damodaran) |
| 公司結構 | 稅率、資本結構、債務成本 Rd | ❌ 算一次固定 | yfinance 財報 + 後備值 |
| **公司營運** | **FCF 成長率 g** | ✅ **只有它變** | 歷史 FCF CAGR 為 Base 錨，上下展開 |

所有房屋假設集中在 [`valuate/dcf_params.py`](valuate/dcf_params.py)，可依自身觀點調整。

**內建護欄**（DCF 最容易自欺的地方，工具會自動警示）：

- 終值成長 g_終 強制 < WACC（否則 Gordon 公式發散）
- 終值佔企業價值 > 80% → 警告「此 DCF 實質在猜終值」
- WACC 落在 6%–12% 外 → 警告參數可能失真
- FCF 年度 vs TTM 分歧 / 歷史波動過大 → 警告可能含一次性項目，建議手動正規化
- 報告附 **WACC × 終值成長敏感度表**，讓你看見估值對假設有多脆

> ⚠️ **資料品質提醒**：DCF 對「基準 FCF」極度敏感，而 yfinance 的免費財報常含一次性項目或缺漏。
> 遇到工具警示時，請務必手動檢視該公司財報、排除一次性項目後再下判斷。

---

## 路線圖

| 階段 | 狀態 | 內容 |
|---|---|---|
| **階段一** | ✅ 完成 | 產業分類表 P/E 估值 / CLI / Excel 輸出 |
| **階段二** | 🚧 進行中 | **FCF 現金流折現法 ✅** / SOTP 業務分拆法 🔜 / 批次 portfolio 🔜 |
| **階段三** | 🔮 研究中 | LLM 動態假設生成（Claude API）|

> 階段二的 **FCF / DCF 法已完成並可使用**（`--method dcf`）。SOTP（業務分拆）與批次
> portfolio 估值為後續工作；DCF 已定義出完整的「假設面」（成長率 / WACC / 終值），
> 階段三的 LLM 屆時可一次性對著最終假設面生成，不需重做。

### 關於階段三（LLM 假設生成）

產業分類表是「靜態」的 — 它不知道某家公司當下有什麼特殊催化劑。階段三會接入 Claude API，根據公司的即時狀況動態生成更精準的三情境假設。

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
│   ├── cli.py                  # 命令列入口 (--method pe/dcf)
│   ├── fetcher.py              # yfinance 資料抓取 (含 DCF 財報 + Rf)
│   ├── sector_map.py           # 產業 → P/E 對照表 (核心 know-how)
│   ├── engine.py               # P/E 法估值引擎 (階段一)
│   ├── dcf.py                  # DCF 法估值引擎 (階段二)
│   ├── wacc.py                 # WACC 計算 + 護欄 (階段二)
│   ├── dcf_params.py           # DCF 房屋假設 (ERP/g_終/護欄)
│   ├── output.py               # 終端 / Excel 輸出 (P/E + DCF)
│   └── assumptions/
│       ├── base.py             # 假設引擎抽象介面
│       ├── sector_based.py     # 階段一：產業分類
│       └── llm_based.py        # 階段三：LLM (預留)
├── examples/
├── tests/
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
