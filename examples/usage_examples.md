# 使用範例

## 基本估值

```bash
$ python -m valuate AAPL

→ 抓取 AAPL ...

================================================================
  AAPL  Apple Inc
================================================================
  產業       : Technology / Consumer Electronics
  現價       : $XXX.XX
  EPS (forward ): $X.XX
  假設來源   : sector_table [industry: Consumer Electronics]

  情境         P/E         目標價        報酬率
  ------------------------------------------
  Bear       18.0x     $XXX.XX       -XX.X%
  Base       26.0x     $XXX.XX       -X.X%
  Bull       34.0x     $XXX.XX       +XX.X%
  ...
```

## 多家公司一次估值 + Excel

```bash
$ python -m valuate NVDA AVGO MRVL --excel --output-dir ./reports
```

會在 `./reports/` 產出三個 xlsx 檔。

## 查看支援的產業

```bash
$ python -m valuate --list-sectors
```

## 調整產業倍數

如果你不同意內建的倍數判斷（例如你認為半導體 Bull 應該給 45x 而非 40x），
直接編輯 `valuate/sector_map.py`：

```python
INDUSTRY_PE_RANGES = {
    "Semiconductors": PERange(18, 28, 45, "..."),  # 把 40 改成 45
    ...
}
```

## 程式化使用 (import 而非 CLI)

```python
from valuate.fetcher import fetch_company
from valuate.engine import ValuationEngine
from valuate.assumptions.sector_based import SectorBasedAssumptions

company = fetch_company("AVGO")
engine = ValuationEngine(SectorBasedAssumptions())
result = engine.value(company)

print(f"Base 目標價: ${result.base_target}")
print(f"Base 報酬率: {result.base_return:.1%}")
```

## 常見問題

**Q: 為什麼某些公司估出來跟分析師差很多？**
A: 產業分類表是通用倍數，沒考慮個別公司的特殊催化劑。差異過大時工具會警示，
   你可以手動調整 `sector_map.py` 或等階段三的 LLM 假設功能。

**Q: 虧損中的公司能估嗎？**
A: P/E 法對 EPS ≤ 0 的公司不適用，工具會照算但加上警示。
   這類公司建議用 P/S 法（階段二規劃中）。

**Q: 支援台股嗎？**
A: 目前只支援美股。台股的資料完整度與代號規則不同，列在未來規劃。
