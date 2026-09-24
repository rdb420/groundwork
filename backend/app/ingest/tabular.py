"""Spreadsheets and delimited text straight to table blocks, one section per sheet. Reading them
natively keeps every row and column, which a trip through PDF would lose."""
import csv
from pathlib import Path

from openpyxl import load_workbook

from ..processing.limits import too_big

MAX_ROWS = 5000  # per sheet; beyond this the sheet is summarised, not copied row by row
MAX_COLS = 40


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return " ".join(str(v).split())


def _trim(rows: list[list[str]]) -> list[list[str]]:
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return rows
    width = max((max((i + 1 for i, c in enumerate(r) if c), default=0) for r in rows), default=0)
    return [r[:width] for r in rows]


def workbook_blocks(path: Path) -> tuple[list[dict], str]:
    """Blocks for each visible and hidden sheet (hidden sheets are marked). Values as last saved;
    formulas are counted by the first read, not repeated here."""
    refused = too_big(path)
    if refused:
        return [], refused
    wb = load_workbook(path, read_only=True, data_only=True)
    out: list[dict] = []
    note = ""
    try:
        for ws in wb.worksheets:
            rows: list[list[str]] = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= MAX_ROWS:
                    note = f"Sheets over {MAX_ROWS} rows were cut short."
                    break
                rows.append([_cell(v) for v in row[:MAX_COLS]])
            rows = _trim(rows)
            hidden = " (hidden sheet)" if ws.sheet_state != "visible" else ""
            out.append({"type": "heading", "text": f"Sheet: {ws.title}{hidden}", "level": 2})
            if rows:
                out.append({"type": "table", "rows": rows, "caption": ""})
            else:
                out.append({"type": "text", "text": "This sheet is empty."})
    finally:
        wb.close()
    return out, note


def delimited_blocks(path: Path) -> tuple[list[dict], str]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    rows: list[list[str]] = []
    note = ""
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        for i, row in enumerate(csv.reader(f, delimiter=delimiter)):
            if i >= MAX_ROWS:
                note = f"Only the first {MAX_ROWS} rows were read."
                break
            rows.append([_cell(v) for v in row[:MAX_COLS]])
    rows = _trim(rows)
    return ([{"type": "table", "rows": rows, "caption": ""}] if rows else []), note
