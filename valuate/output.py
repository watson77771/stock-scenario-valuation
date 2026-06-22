"""
output.py
=========
估值結果的輸出: 終端表格 + xlsx 報告。

  - P/E 法結果 : print_result / write_xlsx
  - DCF 法結果 : print_dcf_result / write_dcf_xlsx   (階段二新增)
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

from . import dcf_params as P


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


# ============================================================
# DCF (階段二) 輸出
# ============================================================

def _sens_header() -> str:
    base_tg = P.TERMINAL_GROWTH["base"]
    cells = "".join(f"{base_tg + d:>11.1%}" for d in P.SENSITIVITY_TG_STEPS)
    return f"    WACC\\g終{cells}"


def print_dcf_result(r) -> None:
    """在終端印出 DCF 估值摘要"""
    w = r.wacc
    print()
    print("=" * 68)
    print(f"  {r.ticker}  {r.name}   [DCF 現金流折現法]")
    print("=" * 68)
    print(f"  產業       : {r.sector or '?'} / {r.industry or '?'}")
    print(f"  現價       : ${r.current_price:,.2f}")
    print(f"  基準 FCF   : ${r.base_fcf / 1e9:,.2f}B  ({r.fcf_source})")
    print(f"  淨負債     : ${r.net_debt / 1e9:,.2f}B")
    print(f"  WACC       : {w.wacc:.2%}  "
          f"(Re={w.cost_of_equity:.1%} / Rd={w.cost_of_debt:.1%} / "
          f"β={w.beta_adj} / 稅={w.tax_rate:.0%} / Rf={w.rf:.2%})")
    print(f"  預測年數   : {r.projection_years} 年")
    print()
    print(f"  {'情境':<8}{'成長g':>8}{'終值g':>8}{'目標價':>14}{'報酬率':>12}{'終值佔比':>10}")
    print("  " + "-" * 60)
    for label, s in (("Bear", r.bear), ("Base", r.base), ("Bull", r.bull)):
        print(f"  {label:<8}{s.growth:>7.1%}{s.terminal_growth:>8.1%}"
              f" ${s.target:>11,.2f} {s.ret:>+10.1%} {s.tv_share:>9.0%}")
    print()

    if r.analyst_target_mean:
        print(f"  分析師均價 : ${r.analyst_target_mean:,.2f} (參考)")

    # 敏感度表
    print()
    print("  敏感度 (Base 情境每股目標價;列=WACC,欄=終值成長 g_終):")
    print(_sens_header())
    for row in r.sensitivity:
        cells = "".join(
            (f"{v:>11,.2f}" if v is not None else f"{'—':>11}")
            for v in row["values"]
        )
        print(f"    {row['wacc']:>7.1%}{cells}")
    print()

    print(f"  理由       : {r.rationale}")

    if r.warnings:
        print()
        print("  ⚠️  警示:")
        for msg in r.warnings:
            print(f"     - {msg}")
    print()


def write_dcf_xlsx(r, output_dir: str = ".") -> str:
    """產出 DCF 估值 xlsx 報告。回傳檔案路徑。"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise ImportError("缺少 openpyxl,請執行: pip install openpyxl")

    wb = Workbook()
    ws = wb.active
    ws.title = f"{r.ticker}_DCF"

    F_TITLE = Font(name="Arial", size=14, bold=True, color="FFFFFF")
    F_HEAD = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    F_BOLD = Font(name="Arial", size=10, bold=True)
    F_BODY = Font(name="Arial", size=10)
    FILL_TITLE = PatternFill("solid", fgColor="385723")     # DCF 用綠色系區別 P/E
    FILL_HEAD = PatternFill("solid", fgColor="70AD47")
    FILL_BEAR = PatternFill("solid", fgColor="FCE4D6")
    FILL_BASE = PatternFill("solid", fgColor="E2EFDA")
    FILL_BULL = PatternFill("solid", fgColor="DDEBF7")
    thin = Side(border_style="thin", color="999999")
    BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
    AL_C = Alignment(horizontal="center", vertical="center")
    AL_L = Alignment(horizontal="left", vertical="center", wrap_text=True)
    AL_R = Alignment(horizontal="right", vertical="center")

    for col, width in [("A", 3), ("B", 22), ("C", 14), ("D", 14), ("E", 14), ("F", 14)]:
        ws.column_dimensions[col].width = width

    def cell(coord, val, font=None, fill=None, align=None, nf=None):
        c = ws[coord]
        c.value = val
        if font: c.font = font
        if fill: c.fill = fill
        if align: c.alignment = align
        c.border = BORDER
        if nf: c.number_format = nf

    w = r.wacc

    # 標題
    ws.merge_cells("B2:F2")
    cell("B2", f"{r.ticker}  {r.name}  — DCF 現金流折現法", F_TITLE, FILL_TITLE, AL_C)
    ws.row_dimensions[2].height = 26
    ws.merge_cells("B3:F3")
    cell("B3", f"產生時間: {datetime.now():%Y-%m-%d %H:%M} | 方法: FCF DCF (階段二)",
         F_BODY, None, AL_C)

    # 基本/WACC 拆解
    cell("B5", "現價 (US$)", F_BOLD, FILL_HEAD, AL_L)
    cell("C5", r.current_price, F_BODY, None, AL_R, "$#,##0.00")
    cell("B6", "基準 FCF (US$)", F_BOLD, FILL_HEAD, AL_L)
    cell("C6", r.base_fcf, F_BODY, None, AL_R, "$#,##0")
    ws.merge_cells("D6:F6")
    cell("D6", r.fcf_source, F_BODY, None, AL_L)
    cell("B7", "淨負債 (US$)", F_BOLD, FILL_HEAD, AL_L)
    cell("C7", r.net_debt, F_BODY, None, AL_R, "$#,##0")
    cell("B8", "WACC", F_BOLD, FILL_HEAD, AL_L)
    cell("C8", w.wacc, F_BODY, None, AL_R, "0.00%")
    ws.merge_cells("D8:F8")
    cell("D8", f"Re={w.cost_of_equity:.1%} Rd={w.cost_of_debt:.1%} "
               f"β={w.beta_adj} 稅={w.tax_rate:.0%} Rf={w.rf:.2%}", F_BODY, None, AL_L)

    # 三情境表
    cell("B10", "情境", F_HEAD, FILL_HEAD, AL_C)
    cell("C10", "Bear 熊", F_HEAD, FILL_HEAD, AL_C)
    cell("D10", "Base 基準", F_HEAD, FILL_HEAD, AL_C)
    cell("E10", "Bull 牛", F_HEAD, FILL_HEAD, AL_C)
    cell("F10", "分析師", F_HEAD, FILL_HEAD, AL_C)

    rows = [
        ("FCF 成長率 g", "growth", "0.0%", None),
        ("終值成長 g_終", "terminal_growth", "0.0%", None),
        ("目標價 (US$)", "target", "$#,##0.00", True),
        ("報酬率", "ret", "0.0%;[Red]-0.0%", None),
        ("終值佔 EV", "tv_share", "0%", None),
    ]
    for i, (label, attr, nf, _bold) in enumerate(rows):
        rr = 11 + i
        cell(f"B{rr}", label, F_BOLD, None, AL_L)
        f = F_BOLD if _bold else F_BODY
        cell(f"C{rr}", getattr(r.bear, attr), f, FILL_BEAR, AL_R, nf)
        cell(f"D{rr}", getattr(r.base, attr), f, FILL_BASE, AL_R, nf)
        cell(f"E{rr}", getattr(r.bull, attr), f, FILL_BULL, AL_R, nf)
        if attr == "target":
            cell(f"F{rr}", r.analyst_target_mean or "—", F_BODY, None, AL_R,
                 "$#,##0.00" if r.analyst_target_mean else None)
        else:
            cell(f"F{rr}", "—", F_BODY, None, AL_C)

    # 敏感度表
    base_tg = P.TERMINAL_GROWTH["base"]
    cell("B17", "敏感度: WACC \\ g_終", F_HEAD, FILL_HEAD, AL_C)
    for j, d in enumerate(P.SENSITIVITY_TG_STEPS):
        cell(f"{chr(67 + j)}17", base_tg + d, F_HEAD, FILL_HEAD, AL_C, "0.0%")
    for i, row in enumerate(r.sensitivity):
        rr = 18 + i
        cell(f"B{rr}", row["wacc"], F_BOLD, None, AL_R, "0.0%")
        for j, v in enumerate(row["values"]):
            cell(f"{chr(67 + j)}{rr}", v if v is not None else "—",
                 F_BODY, None, AL_R, "$#,##0.00" if v is not None else None)

    # 理由
    base_r = 18 + len(r.sensitivity) + 1
    ws.merge_cells(f"B{base_r}:F{base_r}")
    cell(f"B{base_r}", "估值理由", F_HEAD, FILL_HEAD, AL_L)
    ws.merge_cells(f"B{base_r + 1}:F{base_r + 1}")
    cell(f"B{base_r + 1}", r.rationale, F_BODY, None, AL_L)
    ws.row_dimensions[base_r + 1].height = 40

    # 警示
    nxt = base_r + 2
    if r.warnings:
        ws.merge_cells(f"B{nxt}:F{nxt}")
        cell(f"B{nxt}", "⚠️ 警示", None, PatternFill("solid", fgColor="C00000"), AL_L)
        ws[f"B{nxt}"].font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        for i, msg in enumerate(r.warnings):
            rr = nxt + 1 + i
            ws.merge_cells(f"B{rr}:F{rr}")
            cell(f"B{rr}", msg, F_BODY, PatternFill("solid", fgColor="FFE699"), AL_L)
        nxt = nxt + 1 + len(r.warnings)

    # 免責
    ws.merge_cells(f"B{nxt + 1}:F{nxt + 1}")
    cell(f"B{nxt + 1}",
         "本報告由 stock-scenario-valuation 自動產生,為情境分析非投資建議。",
         Font(name="Arial", size=8, italic=True, color="888888"), None, AL_L)

    ts = datetime.now().strftime("%Y%m%d")
    out_path = Path(output_dir) / f"{r.ticker}_DCF_{ts}.xlsx"
    wb.save(out_path)
    return str(out_path)


# ============================================================
# P/E vs DCF 交叉比較 (--method both)
# ============================================================

def print_comparison(pe, dcf) -> None:
    """並排比較 P/E 法與 DCF 法 (任一可為 None)"""
    ref = pe or dcf
    if ref is None:
        print("  ❌ 兩種方法都無法估值")
        return

    price = ref.current_price
    print()
    print("=" * 68)
    print(f"  {ref.ticker}  {ref.name}   [P/E vs DCF 交叉比較]")
    print("=" * 68)
    print(f"  產業       : {ref.sector or '?'} / {ref.industry or '?'}")
    print(f"  現價       : ${price:,.2f}")
    print()
    print(f"  {'方法':<8}{'Bear':>14}{'Base':>14}{'Bull':>14}{'Base報酬':>12}")
    print("  " + "-" * 62)

    if pe is not None:
        print(f"  {'P/E 法':<7}"
              f"${pe.bear_target:>11,.2f} ${pe.base_target:>11,.2f} "
              f"${pe.bull_target:>11,.2f} {pe.base_return:>+10.1%}")
    else:
        print(f"  {'P/E 法':<7}{'(資料不足,略過)':>30}")

    if dcf is not None:
        print(f"  {'DCF 法':<7}"
              f"${dcf.bear.target:>11,.2f} ${dcf.base.target:>11,.2f} "
              f"${dcf.bull.target:>11,.2f} {dcf.base.ret:>+10.1%}")
    else:
        print(f"  {'DCF 法':<7}{'(資料不足,略過)':>30}")

    print()
    if ref.analyst_target_mean:
        print(f"  分析師均價 : ${ref.analyst_target_mean:,.2f} (參考)")

    # 解讀: 兩法 Base 的差異代表什麼
    if pe is not None and dcf is not None and pe.base_target and dcf.base.target:
        diff = dcf.base.target / pe.base_target - 1
        print()
        print(f"  解讀: DCF Base (${dcf.base.target:,.0f}) vs P/E Base "
              f"(${pe.base_target:,.0f}),差異 {diff:+.0%}")
        if abs(diff) <= 0.30:
            print("        → 兩法接近,估值有現金流基本面支撐,可信度較高")
        elif diff < 0:
            print("        → DCF 較保守: 市場用產業倍數給的溢價,基本面現金流暫時撐不起,")
            print("          差距多來自市場對未來成長的想像 (常見於高成長/高品質股)")
        else:
            print("        → DCF 較樂觀: 現金流基本面優於市場給的產業倍數,可能被低估")
    print()
