"""ساخت فایل اکسل styled با خلاصه و نمودار."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..config import AUTHOR, APP_NAME, VERSION
from ..models import PriceRow

HEADER_FILL = PatternFill("solid", fgColor="1E3A5F")
HEADER_FONT = Font(name="Tahoma", size=11, bold=True, color="FFFFFF")
ROW_FONT = Font(name="Tahoma", size=10, color="1F2937")
ALT_FILL = PatternFill("solid", fgColor="F1F5F9")
OK_FILL = PatternFill("solid", fgColor="DCFCE7")
FAIL_FILL = PatternFill("solid", fgColor="FEE2E2")
TITLE_FONT = Font(name="Tahoma", size=16, bold=True, color="1E3A5F")
THIN = Side(style="thin", color="CBD5E1")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

HEADERS = ["سایت", "مدل", "رنگ", "قیمت (تومان)", "وضعیت", "زمان استخراج", "لینک محصول"]


def _style_header(ws, row_index: int, count: int) -> None:
    for col in range(1, count + 1):
        cell = ws.cell(row=row_index, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
    ws.row_dimensions[row_index].height = 28


def _fill_rows_sheet(ws, rows: list[PriceRow]) -> None:
    ws.append(HEADERS)
    _style_header(ws, 1, len(HEADERS))

    for index, row in enumerate(rows, start=2):
        ws.append(list(row.as_tuple()))
        for col in range(1, len(HEADERS) + 1):
            cell = ws.cell(row=index, column=col)
            cell.font = ROW_FONT
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if index % 2 == 0:
                cell.fill = ALT_FILL
        price_cell = ws.cell(row=index, column=4)
        price_cell.number_format = "#,##0"
        price_cell.font = Font(name="Tahoma", size=10, bold=True, color="0F766E")
        status_cell = ws.cell(row=index, column=5)
        status_cell.fill = OK_FILL if row.price else FAIL_FILL
        link_cell = ws.cell(row=index, column=7)
        if row.url:
            link_cell.hyperlink = row.url
            link_cell.font = Font(name="Tahoma", size=9, color="2563EB", underline="single")
        ws.row_dimensions[index].height = 22

    widths = [16, 22, 18, 18, 14, 20, 60]
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{max(2, len(rows) + 1)}"
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False


def _fill_summary_sheet(ws, rows: list[PriceRow]) -> None:
    ws.merge_cells("A1:F1")
    title = ws["A1"]
    title.value = f"خلاصه مقایسه قیمت ها — {APP_NAME}"
    title.font = TITLE_FONT
    title.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 34

    headers = ["مدل", "رنگ", "کمترین (تومان)", "بیشترین (تومان)", "میانگین (تومان)", "ارزان ترین سایت"]
    for col, value in enumerate(headers, start=1):
        ws.cell(row=3, column=col, value=value)
    _style_header(ws, 3, len(headers))

    groups: dict[tuple[str, str], list[PriceRow]] = defaultdict(list)
    for row in rows:
        if row.price:
            groups[(row.model or "—", row.color or "پیش فرض")].append(row)

    chart_rows: list[tuple[str, int]] = []
    row_index = 4
    for (model, color), items in sorted(groups.items()):
        prices = [item.price for item in items if item.price]
        cheapest = min(items, key=lambda item: item.price or 10**12)
        values = [model, color, min(prices), max(prices), round(sum(prices) / len(prices)), cheapest.site]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_index, column=col, value=value)
            cell.font = ROW_FONT
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if row_index % 2 == 0:
                cell.fill = ALT_FILL
            if col in (3, 4, 5):
                cell.number_format = "#,##0"
        chart_rows.append((f"{model} - {color}", min(prices)))
        row_index += 1

    if not groups:
        ws.cell(row=4, column=1, value="داده ای برای نمایش وجود ندارد.").font = ROW_FONT

    for col, width in enumerate([24, 18, 20, 20, 20, 18], start=1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"

    if chart_rows:
        helper_col = 8
        ws.cell(row=3, column=helper_col, value="مدل / رنگ")
        ws.cell(row=3, column=helper_col + 1, value="کمترین")
        for offset, (label, price) in enumerate(chart_rows, start=4):
            ws.cell(row=offset, column=helper_col, value=label)
            ws.cell(row=offset, column=helper_col + 1, value=price)
        ws.column_dimensions[get_column_letter(helper_col)].hidden = True
        ws.column_dimensions[get_column_letter(helper_col + 1)].hidden = True

        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = "کمترین قیمت بر اساس مدل و رنگ"
        chart.y_axis.title = "تومان"
        chart.height = 9
        chart.width = 20
        data = Reference(ws, min_col=helper_col + 1, min_row=3, max_row=3 + len(chart_rows))
        categories = Reference(ws, min_col=helper_col, min_row=4, max_row=3 + len(chart_rows))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(categories)
        chart.legend = None
        ws.add_chart(chart, "H3")


def _fill_report_sheet(ws, rows: list[PriceRow], meta: dict) -> None:
    ws.merge_cells("A1:B1")
    ws["A1"] = f"گزارش اجرا — {APP_NAME}"
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 32

    successes = sum(1 for row in rows if row.price)
    data = [
        ("سازنده", AUTHOR),
        ("نسخه برنامه", VERSION),
        ("تاریخ استخراج", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("تعداد لینک ها", meta.get("jobs", "")),
        ("تعداد ردیف های قیمت", len(rows)),
        ("استخراج موفق", successes),
        ("خطاها", len(rows) - successes),
        ("روش استخراج", "HTTP سریع + مرورگر مخفی به عنوان پشتیبان"),
    ]
    for index, (key, value) in enumerate(data, start=3):
        ws.cell(row=index, column=1, value=key)
        ws.cell(row=index, column=2, value=value)
        ws.cell(row=index, column=1).font = Font(name="Tahoma", size=10, bold=True, color="1E3A5F")
        ws.cell(row=index, column=2).font = ROW_FONT
        ws.cell(row=index, column=1).fill = ALT_FILL
        for col in (1, 2):
            ws.cell(row=index, column=col).border = BORDER
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 50
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False


def export_excel(rows: list[PriceRow], output: Path, meta: dict | None = None) -> Path:
    output = Path(output)
    if output.suffix.lower() != ".xlsx":
        output = output.with_suffix(".xlsx")
    output.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    prices_sheet = workbook.active
    prices_sheet.title = "قیمت ها"
    _fill_rows_sheet(prices_sheet, rows)
    _fill_summary_sheet(workbook.create_sheet("خلاصه"), rows)
    _fill_report_sheet(workbook.create_sheet("گزارش"), rows, meta or {})
    workbook.save(output)
    return output
