"""Парсер экспорта Fritsch ANALYSETTE 22 (лист с таблицей Size / M#### и блоками метаданных).

Столбцы FreqCum / VarCoeff рядом с Size — среднее и коэф. вариации по ВСЕМ измерениям
файла (разным материалам), физического смысла не имеют и игнорируются.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .io_table import _num, excel_serial_to_datetime, read_grids
from .model import Sample

MEAS_COL = re.compile(r"^M\s*(\d+)$")

# нормализованная метка -> ключ метаданных
LABELS = {
    "mess-nr": "meas_no", "meas.nr": "meas_no", "meas.no": "meas_no", "measnr": "meas_no",
    "material": "material",
    "datum": "date", "date": "date",
    "berechnung": "model", "calculation": "model",
    "tradeoff": "tradeoff",
    "strahlabsorption": "obscuration", "beamobscuration": "obscuration",
    "error": "error",
    "ultraschallintensität": "ultrasonics", "ultrasonics": "ultrasonics",
    "pumpengeschwindigkeit": "pump", "pump": "pump",
    "messbereich": "range", "meas.range": "range",
    "mode": "mode", "span": "span", "d[4,3]": "d43_instrument",
}


def _norm(s: str) -> str:
    return re.sub(r"[\s*:]+", "", s).rstrip(".").lower()


def _find_header(rows):
    """Строка-заголовок: первая непустая ячейка 'Size', правее — столбцы M####."""
    for r, row in enumerate(rows):
        cells = [(c, v) for c, v in enumerate(row) if v is not None]
        if not cells or not isinstance(cells[0][1], str) or cells[0][1].strip() != "Size":
            continue
        meas = {}
        for c, v in cells[1:]:
            if isinstance(v, str):
                m = MEAS_COL.match(v.strip())
                if m:
                    meas[int(m.group(1))] = (c, v.strip())
        if meas:
            return r, cells[0][0], meas
    return None


def _values_right(row, c):
    return [v for v in row[c + 1:] if v is not None]


def _parse_meta_blocks(rows, start):
    """Блоки метаданных ниже таблицы: {номер измерения: dict}."""
    blocks, cur = {}, None
    r = start
    while r < len(rows):
        row = rows[r]
        for c, v in enumerate(row):
            if not isinstance(v, str):
                continue
            key = LABELS.get(_norm(v))
            if key is None:
                continue
            vals = _values_right(row, c)
            if key == "meas_no":
                num = next((x for x in vals if _num(x)), None)
                if num is not None:
                    cur = {"percentiles": {}}
                    blocks[int(num)] = cur
                continue
            if cur is None or key in cur:
                continue
            if key in ("material", "model"):
                cur[key] = next((x for x in vals if isinstance(x, str)), None)
            elif key == "date":
                d = next((x for x in vals if not isinstance(x, str)), None)
                cur[key] = excel_serial_to_datetime(d)
            elif key == "tradeoff":
                num = next((x for x in vals if _num(x)), None)
                mode = next((x for x in vals if isinstance(x, str)), None)
                cur[key] = num
                if mode:
                    cur["tradeoff_mode"] = mode
            elif key == "range":
                nums = [x for x in vals if _num(x)][:2]
                cur[key] = tuple(nums)
            else:
                cur[key] = next((x for x in vals if _num(x)), None)
        # таблица перцентилей: строка с 'FreqCum' и 'Size' внутри блока
        if cur is not None:
            labels = {v.strip(): c for c, v in enumerate(row) if isinstance(v, str)}
            if "FreqCum" in labels and "Size" in labels and len(labels) == 2:
                cp, cs = labels["FreqCum"], labels["Size"]
                rr = r + 1
                while rr < len(rows):
                    rw = rows[rr]
                    p = rw[cp] if cp < len(rw) else None
                    s = rw[cs] if cs < len(rw) else None
                    if not (_num(p) and _num(s)):
                        break
                    cur["percentiles"][p] = s
                    rr += 1
                r = rr
                continue
        r += 1
    return blocks


def parse_sheet(rows, sheet: str, file: Path) -> list[Sample]:
    found = _find_header(rows)
    if not found:
        return []
    hr, size_c, meas = found
    # числовые строки под заголовком
    data_rows = []
    for row in rows[hr + 1:]:
        v = row[size_c] if size_c < len(row) else None
        if not _num(v):
            break
        data_rows.append(row)
    if len(data_rows) < 5:
        return []
    blocks = _parse_meta_blocks(rows, hr + 1 + len(data_rows))
    if not blocks:
        return []  # без метаданных это не экспорт прибора
    sizes = np.array([row[size_c] for row in data_rows], dtype=float)
    samples = []
    for no, (c, col_name) in meas.items():
        meta = blocks.get(no)
        if meta is None:
            continue
        cum = np.array([row[c] if c < len(row) and _num(row[c]) else np.nan for row in data_rows])
        if np.isnan(cum).any():
            continue
        name = (meta.get("material") or col_name).strip()
        samples.append(Sample(
            name=name, meas_id=col_name, file=str(file), sheet=sheet, source="fritsch",
            size_um=sizes, cum_pct=cum, meta=meta,
        ))
    return samples


def load_fritsch(path: Path) -> list[Sample]:
    """Все измерения из экспорта Fritsch; листы без блоков метаданных пропускаются."""
    path = Path(path)
    out = []
    for sheet, rows in read_grids(path):
        out.extend(parse_sheet(rows, sheet, path))
    return out
