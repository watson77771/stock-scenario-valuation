"""
sector_map.py
=============
產業分類 → 三情境 P/E 倍數對照表。

這是「階段一」估值假設的核心。yfinance 回傳每家公司的 sector / industry,
本模組把它們對映到合理的 Bear / Base / Bull 本益比範圍。

設計理念:
  - 不同產業的合理估值倍數差異巨大(半導體 vs 能源 vs 金融)
  - 同一產業內,Bull/Base/Bear 反映市場情緒的樂觀/中性/悲觀
  - 這些倍數是「判斷」,使用者可在 config 覆寫

資料來源: 作者(Watson)對多個產業的估值經驗 + 歷史本益比區間。
免責: 這些是經驗法則,非投資建議。市場狀況改變時應調整。
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PERange:
    """單一產業的三情境本益比範圍"""
    bear: float
    base: float
    bull: float
    note: str = ""

    def as_dict(self) -> dict:
        return {"bear": self.bear, "base": self.base, "bull": self.bull, "note": self.note}


# ============================================================
# 產業 P/E 對照表
# ============================================================
# Key 對應 yfinance 的 sector (粗分) 或 industry (細分)
# 細分 industry 優先於粗分 sector
# ============================================================

# --- 細分產業 (industry-level, 優先匹配) ---
INDUSTRY_PE_RANGES: dict[str, PERange] = {
    # 半導體相關 (高成長 + 週期 + AI 題材)
    "Semiconductors": PERange(18, 28, 40, "AI 題材推升 / 週期性強 / 龍頭享溢價"),
    "Semiconductor Equipment & Materials": PERange(16, 24, 34, "設備商 / 跟隨資本支出週期"),

    # 軟體 (ARR 模式 / 高估值容忍)
    "Software - Infrastructure": PERange(22, 34, 48, "基礎架構軟體 / 高黏著度"),
    "Software - Application": PERange(20, 32, 45, "應用軟體 / SaaS ARR 溢價"),

    # 網路 / 媒體
    "Internet Content & Information": PERange(18, 26, 36, "廣告 + 平台 / 受 AI 顛覆與監管影響"),
    "Internet Retail": PERange(20, 32, 50, "電商 / 成長性主導估值"),

    # 硬體 / 設備
    "Consumer Electronics": PERange(18, 26, 34, "品牌溢價 / 如 Apple 類"),
    "Communication Equipment": PERange(14, 20, 28, "網通設備 / 較成熟"),
    "Computer Hardware": PERange(12, 18, 26, "硬體 / 利潤率較低"),

    # 能源 (週期股 / 低估值)
    "Oil & Gas Refining & Marketing": PERange(8, 12, 16, "煉油 / crack spread 週期"),
    "Oil & Gas Integrated": PERange(9, 13, 18, "整合石油 / 受油價主導"),
    "Oil & Gas E&P": PERange(7, 11, 15, "上游探勘 / 高週期"),
    "Uranium": PERange(15, 30, 60, "核能題材 / pre-revenue 故事股波動大"),
    "Solar": PERange(10, 18, 30, "政策驅動 / 補貼敏感"),

    # 金融
    "Banks - Diversified": PERange(8, 11, 14, "大型銀行 / 受利率與監管影響"),
    "Banks - Regional": PERange(7, 10, 13, "區域銀行 / 信用風險敏感"),
    "Credit Services": PERange(12, 18, 26, "支付 / 信用卡 / 成長性較高"),
    "Capital Markets": PERange(10, 15, 22, "投行 / 資產管理 / 市場連動"),
    "Insurance - Diversified": PERange(8, 12, 16, "保險 / 穩健低成長"),

    # 工業 / 國防
    "Aerospace & Defense": PERange(15, 22, 30, "國防 / 訂單能見度高"),
    "Specialty Industrial Machinery": PERange(14, 20, 28, "工業機械 / 跟隨景氣"),

    # 礦業 / 原物料
    "Other Industrial Metals & Mining": PERange(8, 15, 28, "金屬礦 / 商品價格主導 / 高波動"),
    "Lithium": PERange(10, 20, 40, "鋰礦 / EV 需求 + pre-revenue 風險"),

    # 醫療
    "Drug Manufacturers - General": PERange(12, 18, 26, "大藥廠 / 專利懸崖風險"),
    "Biotechnology": PERange(15, 30, 60, "生技 / 臨床結果二元化 / 高波動"),
    "Medical Devices": PERange(18, 26, 36, "醫材 / 穩健成長"),

    # 消費
    "Auto Manufacturers": PERange(8, 18, 35, "車廠 / 傳統低估值但 EV/AI 題材分歧極大"),
    "Restaurants": PERange(18, 25, 35, "餐飲 / 品牌與展店"),
    "Beverages - Non-Alcoholic": PERange(18, 24, 30, "飲料 / 防禦性消費"),

    # Fintech / 加密
    "Financial Data & Stock Exchanges": PERange(15, 25, 38, "金融數據 / 交易所"),
}

# --- 粗分產業 (sector-level, 細分找不到時的 fallback) ---
SECTOR_PE_RANGES: dict[str, PERange] = {
    "Technology": PERange(18, 28, 42, "科技 / 成長性主導"),
    "Communication Services": PERange(15, 24, 36, "通訊服務 / 廣告 + 媒體"),
    "Energy": PERange(8, 12, 17, "能源 / 週期股"),
    "Financial Services": PERange(9, 13, 19, "金融 / 利率敏感"),
    "Healthcare": PERange(14, 22, 32, "醫療 / 防禦 + 創新混合"),
    "Consumer Cyclical": PERange(12, 20, 32, "景氣循環消費"),
    "Consumer Defensive": PERange(16, 22, 28, "防禦性消費 / 穩定"),
    "Industrials": PERange(14, 20, 28, "工業 / 跟隨景氣"),
    "Basic Materials": PERange(9, 15, 26, "原物料 / 商品價格主導"),
    "Real Estate": PERange(12, 18, 26, "房地產 / REITs / 利率敏感"),
    "Utilities": PERange(14, 18, 22, "公用事業 / 防禦低成長"),
}

# --- 最終 fallback (連 sector 都沒有) ---
DEFAULT_PE_RANGE = PERange(12, 18, 26, "通用預設 / 無產業資訊")


def get_pe_range(sector: str | None, industry: str | None) -> tuple[PERange, str]:
    """
    根據 yfinance 的 sector / industry 回傳合理的 P/E 範圍。

    優先順序: industry (細分) > sector (粗分) > default

    Returns:
        (PERange, 匹配層級說明)
    """
    # 1. 先試細分 industry
    if industry and industry in INDUSTRY_PE_RANGES:
        return INDUSTRY_PE_RANGES[industry], f"industry: {industry}"

    # 2. 退而求其次用粗分 sector
    if sector and sector in SECTOR_PE_RANGES:
        return SECTOR_PE_RANGES[sector], f"sector: {sector}"

    # 3. 都沒有,用通用預設
    label = f"default (sector={sector}, industry={industry})"
    return DEFAULT_PE_RANGE, label


def list_supported() -> dict:
    """列出所有支援的產業(供 CLI --list-sectors 用)"""
    return {
        "industries": sorted(INDUSTRY_PE_RANGES.keys()),
        "sectors": sorted(SECTOR_PE_RANGES.keys()),
    }
