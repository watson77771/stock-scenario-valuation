"""
output.py
=========
估值結果的輸出: 終端表格 + xlsx 報告。
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path


def print_result(result) -> None:
    """在終端印出估值摘要"""
    print()
    print("=" * 64)
    print(f"  {result.ticker}  {result.name}")
    print("=" * 64)
    print(f"  產業       : {result.sector or '?'} / {result.industry or '?'}")
    print(f"  現價       : ${result.current_price:,.2f}")
    print(f"  EPS ({result.eps_type:<8}): ${result.eps_used:,.2f}")
    print(f"  假設來源   : {result.source}")
    print()
    print(f"  {'情境':<8}{'P/E':>8}{'目標價':>14}{'報酬率':>12}")
    print("  " + "-" * 42)
    print(f"  {'Bear':<8}{result.bear_pe:>7.1f}x ${result.bear_target:>11,.2f} {result.bear_return:>+10.1%}")
    print(f"  {'Base':<8}{result.base_pe:>7.1f}x ${result.base_target:>11,.2f} {result.base_return:>+10.1%}")
    print(f"  {'Bull':<8}{result.bull_pe:>7.1f}x ${result.bull_target:>11,.2f} {result.bull_return:>+10.1%}")
    print()

    if result.analyst_target_mean:
        print(f"  分析師均價 : ${result.analyst_target_mean:,.2f} (參考)")

    print(f"  理由       : {result.rationale}")

    if result.warnings:
        print()
        print("  ⚠️  警示:")
        for w in result.warnings:
            print(f"     - {w}")
    print()


def write_xlsx(result, output_dir: str = ".") -> str:
    """
    產出 xlsx 報告。

    Returns:
        輸出檔案路徑
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise ImportError("缺少 openpyxl,請執行: pip install openpyxl")

    wb = Workbook()
    ws = wb.active
    ws.title = result.ticker

    # 樣式
    F_TITLE = Font(name="Arial", size=14, bold=True, color="FFFFFF")
    F_HEAD = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    F_BOLD = Font(name="Arial", size=10, bold=True)
    F_BODY = Font(name="Arial", size=10)
    FILL_TITLE = PatternFill("solid", fgColor="1F3864")
    FILL_HEAD = PatternFill("solid", fgColor="5B9BD5")
    FILL_BEAR = PatternFill("solid", fgColor="FCE4D6")
    FILL_BASE = PatternFill("solid", fgColor="E2EFDA")
    FILL_BULL = PatternFill("solid", fgColor="DDEBF7")
    thin = Side(border_style="thin", color="999999")
    BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
    AL_C = Alignment(horizontal="center", vertical="center")
    AL_L = Alignment(horizontal="left", vertical="center", wrap_text=True)
    AL_R = Alignment(horizontal="right", vertical="center")

    for col, w in [("A", 3), ("B", 22), ("C", 14), ("D", 14), ("E", 14), ("F", 14)]:
        ws.column_dimensions[col].width = w

    def cell(coord, val, font=None, fill=None, align=None, nf=None):
        c = ws[coord]
        c.value = val
        if font: c.font = font
        if fill: c.fill = fill
        if align: c.alignment = align
        c.border = BORDER
        if nf: c.number_format = nf

    # 標題
    ws.merge_cells("B2:F2")
    cell("B2", f"{result.ticker}  {result.name}", F_TITLE, FILL_TITLE, AL_C)
    ws.row_dimensions[2].height = 26

    ws.merge_cells("B3:F3")
    cell("B3", f"產生時間: {datetime.now():%Y-%m-%d %H:%M} | 假設來源: {result.source}",
         F_BODY, None, AL_C)

    # 基本資料
    cell("B5", "現價 (US$)", F_BOLD, FILL_HEAD, AL_L)
    cell("C5", result.current_price, F_BODY, None, AL_R, "$#,##0.00")
    cell("B6", f"EPS ({result.eps_type})", F_BOLD, FILL_HEAD, AL_L)
    cell("C6", result.eps_used, F_BODY, None, AL_R, "$#,##0.00")
    cell("B7", "產業", F_BOLD, FILL_HEAD, AL_L)
    ws.merge_cells("C7:F7")
    cell("C7", f"{result.sector or '?'} / {result.industry or '?'}", F_BODY, None, AL_L)

    # 三情境表
    cell("B9", "情境", F_HEAD, FILL_HEAD, AL_C)
    cell("C9", "Bear 熊", F_HEAD, FILL_HEAD, AL_C)
    cell("D9", "Base 基準", F_HEAD, FILL_HEAD, AL_C)
    cell("E9", "Bull 牛", F_HEAD, FILL_HEAD, AL_C)
    cell("F9", "分析師", F_HEAD, FILL_HEAD, AL_C)

    cell("B10", "P/E 倍數", F_BOLD, None, AL_L)
    cell("C10", result.bear_pe, F_BODY, FILL_BEAR, AL_R, '0.0"x"')
    cell("D10", result.base_pe, F_BODY, FILL_BASE, AL_R, '0.0"x"')
    cell("E10", result.bull_pe, F_BODY, FILL_BULL, AL_R, '0.0"x"')
    cell("F10", "—", F_BODY, None, AL_C)

    cell("B11", "目標價 (US$)", F_BOLD, None, AL_L)
    cell("C11", result.bear_target, F_BOLD, FILL_BEAR, AL_R, "$#,##0.00")
    cell("D11", result.base_target, F_BOLD, FILL_BASE, AL_R, "$#,##0.00")
    cell("E11", result.bull_target, F_BOLD, FILL_BULL, AL_R, "$#,##0.00")
    cell("F11", result.analyst_target_mean or "—", F_BODY, None, AL_R,
         "$#,##0.00" if result.analyst_target_mean else None)

    cell("B12", "報酬率", F_BOLD, None, AL_L)
    cell("C12", result.bear_return, F_BODY, FILL_BEAR, AL_R, "0.0%;[Red]-0.0%")
    cell("D12", result.base_return, F_BODY, FILL_BASE, AL_R, "0.0%;[Red]-0.0%")
    cell("E12", result.bull_return, F_BODY, FILL_BULL, AL_R, "0.0%;[Red]-0.0%")
    cell("F12", "—", F_BODY, None, AL_C)

    # 理由
    ws.merge_cells("B14:F14")
    cell("B14", "估值理由", F_HEAD, FILL_HEAD, AL_L)
    ws.merge_cells("B15:F15")
    cell("B15", result.rationale, F_BODY, None, AL_L)
    ws.row_dimensions[15].height = 30

    # 警示
    if result.warnings:
        ws.merge_cells("B17:F17")
        cell("B17", "⚠️ 警示", F_HEAD, PatternFill("solid", fgColor="C00000"), AL_L)
        ws["B17"].font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        for i, w in enumerate(result.warnings):
            r = 18 + i
            ws.merge_cells(f"B{r}:F{r}")
            cell(f"B{r}", w, F_BODY, PatternFill("solid", fgColor="FFE699"), AL_L)

    # 免責
    last_row = 18 + len(result.warnings) + 1
    ws.merge_cells(f"B{last_row}:F{last_row}")
    cell(f"B{last_row}",
         "本報告由 stock-scenario-valuation 自動產生,為情境分析非投資建議。",
         Font(name="Arial", size=8, italic=True, color="888888"), None, AL_L)

    # 存檔
    ts = datetime.now().strftime("%Y%m%d")
    out_path = Path(output_dir) / f"{result.ticker}_valuation_{ts}.xlsx"
    wb.save(out_path)
    return str(out_path)
