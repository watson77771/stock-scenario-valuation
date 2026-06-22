"""
stock-scenario-valuation
========================
股票三情境估值工具 (Bear / Base / Bull)。

輸入任意美股代號,自動抓取財報資料,產出三情境目標價與 xlsx 報告。

估值方法:
  - P/E 法 (階段一): 產業分類對照表決定三情境本益比
  - DCF 法 (階段二): FCF 折現,三情境變動成長率與終值成長

作者: Watson Tsai
授權: MIT
"""

__version__ = "1.1.0"
__author__ = "Watson Tsai"
