"""Calc spreadsheet operations — in-memory model for LibreOffice Calc documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CalcCell:
    """A single cell in a spreadsheet."""

    value: Any = None
    formula: str = ""
    number_format: str = ""


@dataclass
class CalcSheet:
    """A single sheet within a Calc workbook."""

    name: str
    cells: dict[str, CalcCell] = field(default_factory=dict)
    column_widths: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cells": {
                ref: {"value": c.value, "formula": c.formula, "number_format": c.number_format}
                for ref, c in self.cells.items()
            },
            "column_widths": self.column_widths,
        }


@dataclass
class CalcSpreadsheet:
    """In-memory model for a LibreOffice Calc workbook."""

    name: str
    sheets: list[CalcSheet] = field(default_factory=list)

    def get_sheet(self, sheet_name: str) -> CalcSheet:
        for s in self.sheets:
            if s.name == sheet_name:
                return s
        raise KeyError(f"Sheet {sheet_name!r} not found")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "sheets": [s.to_dict() for s in self.sheets]}


def create_spreadsheet(name: str) -> CalcSpreadsheet:
    """Create a new Calc workbook with a default first sheet."""
    wb = CalcSpreadsheet(name=name)
    wb.sheets.append(CalcSheet(name="Sheet1"))
    return wb


def _normalise_ref(cell_ref: str) -> str:
    """Return an upper-cased cell reference, e.g. 'a1' → 'A1'."""
    return cell_ref.strip().upper()


def set_cell(
    spreadsheet: CalcSpreadsheet,
    sheet_name: str,
    cell_ref: str,
    value: Any,
) -> None:
    """Set the value of *cell_ref* in *sheet_name*."""
    sheet = spreadsheet.get_sheet(sheet_name)
    ref = _normalise_ref(cell_ref)
    existing = sheet.cells.get(ref, CalcCell())
    existing.value = value
    sheet.cells[ref] = existing


def get_cell(
    spreadsheet: CalcSpreadsheet,
    sheet_name: str,
    cell_ref: str,
) -> Any:
    """Return the value at *cell_ref* in *sheet_name*, or None if empty."""
    sheet = spreadsheet.get_sheet(sheet_name)
    cell = sheet.cells.get(_normalise_ref(cell_ref))
    return cell.value if cell else None


def set_formula(
    spreadsheet: CalcSpreadsheet,
    sheet_name: str,
    cell_ref: str,
    formula: str,
) -> None:
    """Store a formula string at *cell_ref* in *sheet_name*."""
    sheet = spreadsheet.get_sheet(sheet_name)
    ref = _normalise_ref(cell_ref)
    existing = sheet.cells.get(ref, CalcCell())
    existing.formula = formula
    sheet.cells[ref] = existing


def add_sheet(spreadsheet: CalcSpreadsheet, name: str) -> CalcSheet:
    """Append a new sheet named *name*."""
    for s in spreadsheet.sheets:
        if s.name == name:
            raise ValueError(f"Sheet {name!r} already exists")
    new_sheet = CalcSheet(name=name)
    spreadsheet.sheets.append(new_sheet)
    return new_sheet


def delete_sheet(spreadsheet: CalcSpreadsheet, name: str) -> CalcSheet:
    """Remove the sheet named *name* and return it."""
    for i, s in enumerate(spreadsheet.sheets):
        if s.name == name:
            return spreadsheet.sheets.pop(i)
    raise KeyError(f"Sheet {name!r} not found")


def set_column_width(
    spreadsheet: CalcSpreadsheet,
    sheet_name: str,
    col: str,
    width_chars: int,
) -> None:
    """Set the display width of column *col* (e.g. 'A') in characters."""
    sheet = spreadsheet.get_sheet(sheet_name)
    sheet.column_widths[col.upper()] = width_chars


def apply_number_format(
    spreadsheet: CalcSpreadsheet,
    sheet_name: str,
    range_ref: str,
    format_code: str,
) -> None:
    """Apply *format_code* to all cells in *range_ref*.

    Supports single cell references (e.g. 'A1') or simple column ranges
    (e.g. 'A1:C10').  The format code is stored on each matching cell.
    """
    sheet = spreadsheet.get_sheet(sheet_name)
    refs = _expand_range(range_ref)
    for ref in refs:
        existing = sheet.cells.get(ref, CalcCell())
        existing.number_format = format_code
        sheet.cells[ref] = existing


def sort_range(
    spreadsheet: CalcSpreadsheet,
    sheet_name: str,
    range_ref: str,
    col_index: int,
    ascending: bool = True,
) -> None:
    """Sort *range_ref* by column at offset *col_index* (0-based).

    This operates on the in-memory cell data only.
    """
    sheet = spreadsheet.get_sheet(sheet_name)
    refs = _expand_range(range_ref)
    if not refs:
        return

    col_letters = _col_letters_in_range(range_ref)
    row_numbers = sorted({_row_number(r) for r in refs})

    if col_index >= len(col_letters):
        raise IndexError(f"col_index {col_index} out of range for {len(col_letters)} columns")

    sort_col = col_letters[col_index]
    rows_data: list[tuple[int, dict[str, CalcCell]]] = []
    for row in row_numbers:
        row_cells = {}
        for col in col_letters:
            ref = f"{col}{row}"
            row_cells[col] = sheet.cells.get(ref, CalcCell())
        key_cell = row_cells.get(sort_col, CalcCell())
        rows_data.append((row, row_cells, str(key_cell.value or "")))

    rows_data.sort(key=lambda x: x[2], reverse=not ascending)

    for new_idx, (orig_row, row_cells, _) in enumerate(rows_data):
        target_row = row_numbers[new_idx]
        for col in col_letters:
            sheet.cells[f"{col}{target_row}"] = row_cells[col]


# ---------------------------------------------------------------------------
# Helpers

def _expand_range(range_ref: str) -> list[str]:
    """Expand an A1 or A1:C10 reference into individual cell references."""
    range_ref = range_ref.upper().strip()
    if ":" not in range_ref:
        return [range_ref]
    start, end = range_ref.split(":")
    start_col, start_row = _split_ref(start)
    end_col, end_row = _split_ref(end)

    col_a = _col_to_num(start_col)
    col_b = _col_to_num(end_col)
    refs = []
    for col_n in range(col_a, col_b + 1):
        for row_n in range(start_row, end_row + 1):
            refs.append(f"{_num_to_col(col_n)}{row_n}")
    return refs


def _col_letters_in_range(range_ref: str) -> list[str]:
    """Return a sorted list of column letters present in *range_ref*."""
    range_ref = range_ref.upper().strip()
    if ":" not in range_ref:
        return [_split_ref(range_ref)[0]]
    start, end = range_ref.split(":")
    start_col, _ = _split_ref(start)
    end_col, _ = _split_ref(end)
    col_a = _col_to_num(start_col)
    col_b = _col_to_num(end_col)
    return [_num_to_col(n) for n in range(col_a, col_b + 1)]


def _split_ref(ref: str) -> tuple[str, int]:
    m = re.match(r"([A-Z]+)(\d+)", ref)
    if not m:
        raise ValueError(f"Invalid cell reference: {ref!r}")
    return m.group(1), int(m.group(2))


def _row_number(ref: str) -> int:
    return _split_ref(ref)[1]


def _col_to_num(col: str) -> int:
    num = 0
    for ch in col:
        num = num * 26 + (ord(ch) - ord("A") + 1)
    return num


def _num_to_col(num: int) -> str:
    result = ""
    while num > 0:
        num, rem = divmod(num - 1, 26)
        result = chr(ord("A") + rem) + result
    return result
