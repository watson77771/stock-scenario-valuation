# stock-scenario-valuation

> 輸入任意美股代號，自動抓取財報資料，套用產業分類倍數，產出 **Bear / Base / Bull 三情境**目標價與 Excel 報告。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**作者**：Watson Tsai

---

## ⚠️ 目前版本說明（請先讀這段）

**現階段（v1 / 階段一）的估值假設來自「產業分類固定倍數表」，不是針對個別公司的智慧判斷。**

這代表：

- 同一產業的所有公司，套用**同一組** Bear / Base / Bull 本益比（例如所有半導體股都用 18 / 28 / 40x）
- 工具**不會**讀取個別公司的新聞、催化劑、護城河等特殊因素
- 因此對「產業中的特殊公司」可能失準。例如 Apple 的品牌與服務溢價讓市場給它高於同業的倍數，但產業表會把它當成普通消費電子公司，估值偏保守

**這是設計上的取捨，不是 bug** —— 換來的是免費、瞬間、透明、可手動調整。你隨時可以編輯 [`valuate/sector_map.py`](valuate/sector_map.py) 來覆寫你不同意的倍數。

📍 **未來規劃**：作者將於近期接入 LLM（Claude API），讓使用者可根據個別公司的即時狀況動態生成更精準的假設。詳見下方[路線圖](#路線圖)。

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
  產業       : Technology / Semiconductors
  現價       : $433.62
  EPS (forward): $13.50
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
git clone https://github.com/watson77771/stock-scenario-valuation.git
cd stock-scenario-valuation
pip install -r requirements.txt
```

需求：Python 3.10+

---

## 使用方式

```bash
# 估值單一公司 (終端輸出)
python -m valuate AVGO

# 同時產出 Excel 報告
python -m valuate AVGO --excel

# 一次估值多家公司
python -m valuate NVDA TSLA AAPL --excel

# 指定 Excel 輸出目錄
python -m valuate AVGO --excel --output-dir ./reports

# 列出所有支援的產業分類
python -m valuate --list-sectors
```

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
| 能源（煉油） | 8x | 12x | 16x |
| 金融（銀行） | 8x | 11x | 14x |

yfinance 回傳公司的 sector / industry，工具自動歸類套用。找不到對應產業時，使用通用預設 12 / 18 / 26x。

**這些倍數是經驗法則，你可以也應該根據自己的判斷調整** —— 直接編輯 `valuate/sector_map.py`。

---

## 路線圖

| 階段 | 狀態 | 內容 |
|---|---|---|
| **階段一** | ✅ 完成 | 產業分類表估值 / CLI / Excel 輸出 |
| **階段二** | 🔜 規劃中 | SOTP 業務分拆法 / FCF 法 / 批次 portfolio |
| **階段三** | 🔮 研究中 | LLM 動態假設生成（Claude API）|

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
│   ├── cli.py                  # 命令列入口
│   ├── fetcher.py              # yfinance 資料抓取
│   ├── sector_map.py           # 產業 → P/E 對照表 (核心 know-how)
│   ├── engine.py               # 估值引擎
│   ├── output.py               # 終端 / Excel 輸出
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
