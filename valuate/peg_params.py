"""
peg_params.py
=============
PEG (本益成長比 | Price/Earnings-to-Growth) 與「成長校正目標價」的房屋假設。

PEG 的核心: 用成長率去解釋本益比合不合理。它補的是 DCF 看不到、P/E 法只間接含的
「市場願意為成長多付的溢價」。但 PEG 只對「正成長、獲利穩定的成長型公司」有意義,
對零成長/負成長/景氣循環/金融/虧損股會給出垃圾值 —— 所以本檔同時定義 gating 門檻。

設計原則 (與 dcf_params 一致):
  - 三情境只變「目標 PEG」(市場願意為每單位成長付幾倍),成長率本身是估計值不變動
  - 所有數字皆為「判斷」,使用者應依自身觀點調整
"""

from __future__ import annotations


# ============================================================
# 成長校正目標價: target = (成長率% × 目標PEG) × EPS
# ============================================================
# 目標 PEG = 市場願意為每 1% 成長付幾倍本益比。
#   PEG=1 (Lynch 經典「合理」) / 1.5 (優質成長常態) / 2.0 (題材發酵容忍上限)
# 三情境只變這個倍數,反映市場情緒的保守 / 中性 / 樂觀。
TARGET_PEG = {
    "bear": 1.0,
    "base": 1.5,
    "bull": 2.0,
}


# ============================================================
# Gating (適用性護欄) —— PEG 最容易自欺的地方
# ============================================================
# 成長率低於此 → PEG 失真 (分母太小,PEG 爆大且無意義);標警示,不產目標價
PEG_MIN_GROWTH = 0.05          # 年成長 < 5% 視為「低成長」,PEG 不適用
# 成長率高於此 → 超高成長不可持續,PEG 樂觀失真;標警示但仍計算
PEG_MAX_GROWTH = 0.50          # 年成長 > 50% 視為「超高成長」,PEG 參考性下降
# 用於成長校正的成長率,最終仍夾在這個合理區間 (避免極端值產生荒謬目標價)
GROWTH_CLAMP = (0.0, 0.40)

# 成長率年期: 歷史與未來都優先取「3~5 年」窗口 (穩定、可驗證)
GROWTH_WINDOW_YEARS = 5        # 最多取近/未來 5 年
GROWTH_WINDOW_MIN = 3          # 至少要 3 年才算,否則視為資料不足

# EPS ≤ 0 (虧損) → 本益比無意義,該腿 (trailing 或 forward) 不計算
# (在引擎內以 eps > 0 判斷,不需參數)

# 景氣循環 / 金融 / 受監管低成長產業: EPS 成長代表性低,PEG 參考性弱 → 標警示。
# 以 yfinance 的 sector / industry 名稱比對。
PEG_WEAK_SECTORS = {
    "Energy",
    "Basic Materials",
    "Financial Services",
    "Utilities",
    "Real Estate",
}
PEG_WEAK_INDUSTRIES = {
    "Oil & Gas Refining & Marketing",
    "Oil & Gas Integrated",
    "Oil & Gas E&P",
    "Banks - Diversified",
    "Banks - Regional",
    "Insurance - Diversified",
    "Auto Manufacturers",       # EV/AI 題材使 EPS 成長極不穩定
    "Other Industrial Metals & Mining",
}
