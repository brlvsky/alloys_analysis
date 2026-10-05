"""Распознавание распределения в произвольной таблице: экспорты разных приборов и таблицы, набранные руками.

Что понимается (на каждом листе, по столбцам и — если так лучше — по строкам, т. е. таблица «боком»):

* ось размеров — строго возрастающий ИЛИ убывающий ряд неотрицательных чисел (≥ 5 значений) либо
  столбец диапазонов текстом («15–45», «−45+20», «<20», «>500», «поддон»; ≥ 3 строк);
* единицы размеров — из заголовка или из самих ячеек: мкм (по умолчанию), мм, нм, меш (ASTM E11);
* распределение рядом с осью:
    - накопленная «мельче размера» (проход, ΣQ, undersize) — не убывает, доходит до ~100;
    - накопленная «крупнее размера» (остаток на сите, R, oversize) — пересчитывается: Q = 100 − R;
    - доли по интервалам (сумма ~100): при размерах по возрастанию доля относится к интервалу,
      ЗАКАНЧИВАЮЩЕМУСЯ на этом размере (так пишут лазерные анализаторы); при размерах по убыванию
      (ситовой анализ) — к частицам КРУПНЕЕ этого сита и мельче предыдущего (остаток на сите);
      если значений на одно меньше, чем размеров, — размеры считаются границами интервалов;
    - плотность q3 (по lg x или ln x; только если так подписан столбец) — интегрируется;
    - доли единицы (0…1) переводятся в проценты;
* числа текстом («12,5», «12.5 %», «1 234,5»), несколько образцов со своими столбцами размеров,
  несколько таблиц на листе одна под другой.

Кривые никогда не обрезаются и не перенормируются. Каждое допущение записывается в
sample.meta["import_notes"] — программа показывает его в журнале и в свойствах образца.
Если автоматически не получилось, есть ручной импорт по «рецепту» (parse_recipe).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .model import INFO, Sample

MIN_POINTS = 5          # минимум точек в оси размеров (числовой)
MIN_RANGES = 3          # минимум строк в оси-диапазонах
CUM_LAST_MIN = 90.0     # накопленная кривая должна дойти хотя бы до этого (если не подписана явно)

GENERIC_HEADERS = {
    "freqcum", "q", "q,%", "q, %", "%", "σq", "σq,%", "σq, %", "q3", "cum", "cumulative",
    "sumq", "накопл", "накопленная", "доля", "value", "values", "y", "tt", "q3,%", "q3, %", "δq", "dq",
    "volume", "volume%", "vol%", "vol, %", "объём", "объем", "масса", "mass", "passing", "проход",
    "undersize", "oversize", "остаток", "retained", "%pass", "% pass", "%chan", "% chan", "q(%)",
    "undersize(%)", "volume density (%)", "volume density", "% passing", "% retained",
}
GENERIC_SHEETS = {"лист1", "sheet1", "лист", "sheet", "data", "данные", "лист2", "sheet2", "лист3", "sheet3"}

# стандартные сита ASTM E11 (номер меш → номинальное отверстие, мкм)
ASTM_E11_MESH = {
    4: 4750, 5: 4000, 6: 3350, 7: 2800, 8: 2360, 10: 2000, 12: 1700, 14: 1400, 16: 1180, 18: 1000,
    20: 850, 25: 710, 30: 600, 35: 500, 40: 425, 45: 355, 50: 300, 60: 250, 70: 212, 80: 180,
    100: 150, 120: 125, 140: 106, 170: 90, 200: 75, 230: 63, 270: 53, 325: 45, 400: 38, 450: 32,
    500: 25, 635: 20,
}

SIZE_WORDS = ("size", "размер", "диаметр", "diameter", "сито", "sieve", "mesh", "меш", "фракц", "fraction",
              "x0", "x /", "x/", "class", "класс", "ячейк", "aperture", "channel", "канал", "мкм", "µm", "μm",
              "micron", "микрон")
CUM_WORDS = ("накоп", "cum", "σq", "Σq", "sum", "passing", "проход", "undersize", "мельче", "q3/%", "q3 /", "%pass",
             "q(x)", "q3(x)", "freqcum")
RES_WORDS = ("остат", "retain", "oversize", "крупнее", "residue", "на сите", "r(x)", "r,", "r %", "r(%)")
DENS_WORDS = ("q3lg", "q3*", "плотн", "density", "dq/dlg", "dq/dlog", "dq/dln", "q3(lg", "q3 lg", "dlog")
DENS_LN_WORDS = ("dln", "q3*(ln", "/dln", "по ln", "(ln")


# ==================================================================== ячейки
@dataclass(frozen=True)
class Rng:
    """Диапазон размеров из текста: «15–45» → (15, 45); «<20» → (0, 20); «>500» → (500, inf);
    «поддон» → (0, nan) — верхняя граница определяется по таблице."""
    lo: float
    hi: float
    unit: float | None = None


_N = r"\d+(?:[   ]\d{3})*(?:[.,]\d+)?|\d*[.,]\d+"
_UNIT_RE = (r"мкм|µm|μm|um|micron[s]?|микрон[а-я]*|мк|мм|mm|нм|nm")
_UNITS = {"мкм": 1.0, "µm": 1.0, "μm": 1.0, "um": 1.0, "micron": 1.0, "microns": 1.0, "мк": 1.0,
          "мм": 1000.0, "mm": 1000.0, "нм": 1e-3, "nm": 1e-3}


def _unit_factor(u: str | None) -> float | None:
    if not u:
        return None
    u = u.lower()
    if u.startswith("микрон"):
        return 1.0
    return _UNITS.get(u)


def _f(s: str) -> float:
    s = re.sub(r"[   ]", "", s)
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:      # 1,234.5 — запятая-разделитель тысяч
        s = s.replace(",", "")
    return float(s)


def parse_text(s: str):
    """Текст ячейки → float | Rng | исходная строка."""
    t = s.strip().strip('"').strip()
    if not t:
        return None
    low = t.lower()
    if low in ("поддон", "pan", "дно", "bottom", "пыль", "dust", "<", "мелочь"):
        return Rng(0.0, math.nan)
    unit = None
    m = re.search(rf"\s*\(?({_UNIT_RE})\)?\.?\s*$", t, flags=re.I)
    if m and re.search(r"\d", t[:m.start()]):
        unit = _unit_factor(m.group(1))
        t = t[:m.start()].strip()
    t = t.replace("−", "-").replace("–", "-").replace("—", "-").replace("÷", "-").replace("…", "-")
    t = re.sub(r"\.\.\.?", "-", t)
    # число, возможно с %
    m = re.fullmatch(rf"(-?)\s*({_N})\s*%?", t)
    if m:
        v = -_f(m.group(2)) if m.group(1) else _f(m.group(2))
        return v if unit is None else Rng(v, v, unit)      # «45 мкм» — число с единицами
    # −45+20 / -45 +20 (ситовая запись: прошло через 45, осталось на 20)
    m = re.fullmatch(rf"-\s*({_N})\s*\+\s*({_N})", t) or re.fullmatch(rf"\+\s*({_N})\s*-\s*({_N})", t)
    if m:
        a, b = _f(m.group(1)), _f(m.group(2))
        return Rng(min(a, b), max(a, b), unit)
    # a-b, a to b
    m = re.fullmatch(rf"({_N})\s*(?:-|to|до)\s*({_N})", t, flags=re.I)
    if m:
        a, b = _f(m.group(1)), _f(m.group(2))
        if a != b:
            return Rng(min(a, b), max(a, b), unit)
    m = re.fullmatch(rf"(?:<|≤|<=|менее|меньше|до|below|under|-)\s*({_N})", t, flags=re.I)
    if m:
        return Rng(0.0, _f(m.group(1)), unit)
    m = re.fullmatch(rf"(?:>|≥|>=|более|больше|свыше|above|over|\+)\s*({_N})", t, flags=re.I)
    if m:
        return Rng(_f(m.group(1)), math.inf, unit)
    return s


def normalize(rows: list[list]) -> list[list]:
    """Текстовые числа → float, диапазоны → Rng; прочее (текст, даты, None) — как есть."""
    out = []
    for row in rows:
        new = []
        for v in row:
            if isinstance(v, str):
                v = parse_text(v)
            elif isinstance(v, bool):
                v = float(v)
            elif isinstance(v, int):
                v = float(v)
            new.append(v)
        out.append(new)
    return out


def _num(v) -> bool:
    return isinstance(v, float) and math.isfinite(v)


def _point(v):
    """Число или «число с единицами» → (значение, единицы|None); иначе None."""
    if _num(v):
        return v, None
    if isinstance(v, Rng) and v.lo == v.hi and math.isfinite(v.lo):
        return v.lo, v.unit
    return None


def _is_range(v) -> bool:
    return isinstance(v, Rng) and not (v.lo == v.hi)


# ==================================================================== ось размеров
@dataclass
class Axis:
    col: int
    r0: int
    n: int                    # число строк оси (включая строки-диапазоны по краям)
    kind: str                 # "num" | "range"
    sizes: list               # значения (мкм после пересчёта единиц) или Rng
    direction: int = 1        # +1 по возрастанию, −1 по убыванию (для "num")
    header: str = ""
    notes: tuple = ()
    lead: object = None       # диапазон-строка перед числовой осью («+500»)
    tail: object = None       # диапазон-строка после числовой оси («поддон», «<45»)

    @property
    def rows(self) -> range:
        return range(self.r0, self.r0 + self.n)


def _col(rows, c):
    return [row[c] if c < len(row) else None for row in rows]


def _text_above(rows, c, r0, depth=8, skip_numbers=False) -> str:
    for r in range(r0 - 1, max(-1, r0 - 1 - depth), -1):
        v = rows[r][c] if c < len(rows[r]) else None
        if isinstance(v, str) and v.strip():
            return v.strip()
        if v is not None and not skip_numbers:
            return ""
    return ""


def _has(text: str, words) -> bool:
    t = (text or "").lower().replace("ё", "е")
    return any(w.lower() in t for w in words)


def _header_unit(text: str):
    """Единицы оси по заголовку: (множитель → мкм | 'mesh' | None, заметка)."""
    t = (text or "").lower()
    if "mesh" in t or "меш" in t:
        return "mesh", "размеры в меш переведены в мкм по стандартным ситам ASTM E11"
    if re.search(r"(?<![a-zа-я])(мм|mm)(?![a-zа-я])", t):
        return 1000.0, "размеры в мм переведены в мкм (×1000)"
    if re.search(r"(?<![a-zа-я])(нм|nm)(?![a-zа-я])", t):
        return 1e-3, "размеры в нм переведены в мкм (÷1000)"
    return None, ""


def _num_runs(col):
    """Максимальные строго монотонные ряды неотрицательных чисел: [(r0, n, направление)]."""
    runs = []
    i, N = 0, len(col)
    while i < N:
        p = _point(col[i])
        if p is None or p[0] < 0:
            i += 1
            continue
        j = i + 1
        d = 0
        while j < N:
            q = _point(col[j])
            if q is None or q[0] < 0:
                break
            prev = _point(col[j - 1])[0]
            step = 1 if q[0] > prev else -1 if q[0] < prev else 0
            if step == 0 or (d and step != d):
                break
            d = step
            j += 1
        if j - i >= MIN_POINTS and d:
            runs.append((i, j - i, d))
            i = j
        else:
            i += 1
    return runs


def _range_cell(v) -> bool:
    return _is_range(v) or _ok_point(v) or (_num(v) and v < 0)


def _range_runs(col):
    """Столбцы фракций текстом; отрицательное число в таком столбце — запись «−20» (прошло через 20)."""
    runs, i, N = [], 0, len(col)
    while i < N:
        if not _range_cell(col[i]):
            i += 1
            continue
        j = i
        while j < N and _range_cell(col[j]):
            j += 1
        k = sum(_is_range(col[x]) for x in range(i, j))
        if k >= MIN_RANGES and k >= (j - i) * 0.6:
            runs.append((i, j - i))
        i = j
    return runs


def _ok_point(v):
    p = _point(v)
    return p is not None and p[0] >= 0


def find_axes(rows) -> list[Axis]:
    ncols = max((len(r) for r in rows), default=0)
    axes = []
    for c in range(ncols):
        col = _col(rows, c)
        used = set()
        for r0, n in _range_runs(col):
            header = _text_above(rows, c, r0)
            hu, note = _header_unit(header)
            items = []
            for v in col[r0:r0 + n]:
                if _is_range(v):
                    items.append(v)
                elif _num(v) and v < 0:
                    items.append(Rng(0.0, -v))
                else:
                    x, u = _point(v)
                    items.append(Rng(x, x, u))
            axes.append(Axis(c, r0, n, "range", items, header=header, notes=(note,) if note else ()))
            used.update(range(r0, r0 + n))
        for r0, n, d in _num_runs(col):
            if any(r in used for r in range(r0, r0 + n)):
                continue
            header = _text_above(rows, c, r0)
            vals, units = [], set()
            for v in col[r0:r0 + n]:
                x, u = _point(v)
                vals.append(x)
                if u is not None:
                    units.add(u)
            ax = Axis(c, r0, n, "num", vals, d, header=header)
            # строки-диапазоны по краям числовой оси (ситовой анализ: «+500» сверху, «поддон» снизу)
            if r0 > 0 and isinstance(col[r0 - 1], Rng) and _is_range(col[r0 - 1]):
                ax.lead, ax.r0, ax.n = col[r0 - 1], r0 - 1, ax.n + 1
            end = r0 + n
            if end < len(col) and isinstance(col[end], Rng) and _is_range(col[end]):
                ax.tail, ax.n = col[end], ax.n + 1
            if ax.lead is not None or ax.tail is not None:
                ax.header = _text_above(rows, c, ax.r0) or header
            hu, note = _header_unit(ax.header)
            notes = []
            if hu == "mesh":
                try:
                    ax.sizes = [float(ASTM_E11_MESH[int(round(x))]) for x in vals]
                except KeyError:
                    continue   # не стандартные номера сит — не ось
                notes.append(note)
                ax.direction = 1 if ax.sizes[-1] > ax.sizes[0] else -1
            else:
                f = hu if hu is not None else (units.pop() if len(units) == 1 else None)
                if f is not None and f != 1.0:
                    ax.sizes = [x * f for x in vals]
                    notes.append(note or ("размеры в мм переведены в мкм (×1000)" if f == 1000.0 else
                                          "размеры в нм переведены в мкм (÷1000)"))
            ax.notes = tuple(notes)
            axes.append(ax)
    return axes


# ==================================================================== распределение рядом с осью
@dataclass
class Curve:
    sizes: np.ndarray
    cum: np.ndarray
    kind: str                 # cum | residue | int | edges | sieve | ranges | density
    notes: tuple = ()


def _scaled(vals):
    """Варианты масштаба: как есть и ×100 (доли единицы)."""
    yield np.asarray(vals, float), ""
    if np.nanmax(np.abs(vals)) <= 1.0 + 1e-9:
        yield np.asarray(vals, float) * 100.0, "доли единицы переведены в проценты (×100)"


def _cum_ok(v, hinted):
    if len(v) < 2 or np.any(np.diff(v) < -0.05) or v[0] > 50 or v[-1] > 101.0:
        return False
    return v[-1] >= (50.0 if hinted else CUM_LAST_MIN)


def classify(axis: Axis, values: list, offset: int, header: str) -> Curve | None:
    """values — числа столбца распределения на строках оси, начиная с offset (0 или 1)."""
    if axis.kind == "range":
        return _from_ranges(axis, values, header)
    xs = np.asarray(axis.sizes, float)
    nlead = 1 if axis.lead is not None else 0
    num_rows = len(xs)
    # значения только на числовых строках оси (строки-диапазоны по краям — отдельно)
    vals = np.asarray(values, float)
    v_lead = v_tail = None
    if nlead and offset == 0 and len(vals) >= 1:
        v_lead, vals = vals[0], vals[1:]
    elif nlead and offset == 1:
        pass
    if axis.tail is not None and len(vals) > num_rows:
        v_tail, vals = vals[num_rows], vals[:num_rows]
    hint_cum, hint_res, hint_den = _has(header, CUM_WORDS), _has(header, RES_WORDS), _has(header, DENS_WORDS)
    asc = axis.direction > 0
    order = slice(None) if asc else slice(None, None, -1)
    x = xs[order]
    notes = list(axis.notes)
    if not asc:
        notes.append("размеры шли по убыванию — таблица развёрнута")

    if len(vals) == num_rows:
        v_all = vals[order]
        for v, sc in _scaled(v_all):
            extra = [sc] if sc else []
            if not hint_res and not hint_den and _cum_ok(v, hint_cum):
                return Curve(x, v, "cum", tuple(notes + extra))
            r = 100.0 - v
            if not hint_cum and not hint_den and _cum_ok(r, hint_res) and v[0] >= 50:
                return Curve(x, r, "residue", tuple(notes + extra + [
                    "накопленный остаток на сите (крупнее размера) пересчитан: ΣQ = 100 − R"]))
        if hint_den:
            c = _integrate_density(x, v_all, header)
            if c is not None:
                return Curve(x, c[0], "density", tuple(notes + [c[1]]))
        for v, sc in _scaled(v_all):
            extra = [sc] if sc else []
            pan = 0.0 if v_tail is None else float(v_tail) * (100.0 if sc else 1.0)
            top = 0.0 if v_lead is None else float(v_lead) * (100.0 if sc else 1.0)
            total = v.sum() + pan + top
            if np.all(v >= -1e-9) and 90.0 <= total <= 105.0:
                if asc:
                    return Curve(x, np.cumsum(v), "int", tuple(notes + extra + [
                        "доли по интервалам: доля в строке — интервал, заканчивающийся на этом размере"]))
                # ситовой анализ: остаток на сите x_i = частицы от x_i до следующего (крупнее) сита
                cum = pan + np.concatenate([[0.0], np.cumsum(v)[:-1]])
                if not asc and axis.tail is not None and v_tail is not None:
                    notes.append("строка «поддон / мельче» учтена как доля мельче самого мелкого сита")
                return Curve(x, cum, "sieve", tuple(notes + extra + [
                    "доли по ситам: доля в строке — остаток на этом сите (крупнее его и мельче предыдущего)"]))
        return None

    if len(vals) == num_rows - 1:   # значений на одно меньше: размеры — границы интервалов
        v_all = vals if asc else vals[::-1]
        for v, sc in _scaled(v_all):
            extra = [sc] if sc else []
            if np.all(v >= -1e-9) and 90.0 <= v.sum() <= 105.0:
                return Curve(x, np.concatenate([[0.0], np.cumsum(v)]), "edges", tuple(notes + extra + [
                    "размеров на один больше, чем долей: размеры — границы интервалов"]))
    return None


def _integrate_density(x, q, header):
    """q3 по lg x (или ln x, если так подписано) → накопленная; принимаем, если интеграл 85–110 %."""
    if np.any(q < -1e-9) or np.any(x <= 0) or len(x) < MIN_POINTS:
        return None
    ln = _has(header, DENS_LN_WORDS)
    t = np.log(x) if ln else np.log10(x)
    for scale in (1.0, 100.0):
        cum = np.concatenate([[0.0], np.cumsum((q[1:] + q[:-1]) / 2 * np.diff(t))]) * scale
        if 85.0 <= cum[-1] <= 110.0:
            return cum, (f"плотность q3 по {'ln' if ln else 'lg'} x проинтегрирована в накопленную кривую "
                         f"(без перенормировки; итог {cum[-1]:.1f} %)")
    return None


def _from_ranges(axis: Axis, values, header) -> Curve | None:
    rngs = list(axis.sizes)
    vals = np.asarray(values, float)
    if len(vals) != len(rngs):
        return None
    for v, sc in _scaled(vals):
        if not (np.all(v >= -1e-9) and 90.0 <= v.sum() <= 105.0):
            continue
        hu, unote = _header_unit(axis.header)
        f = hu if isinstance(hu, float) else 1.0
        items = []
        finite_lo = [r.lo for r in rngs if r.lo > 0 and math.isfinite(r.lo)]
        for r, w in zip(rngs, v):
            uf = r.unit if r.unit is not None else f
            lo, hi = r.lo * uf, r.hi * uf if math.isfinite(r.hi) else r.hi
            if r.lo == r.hi:                      # одиночное число в столбце диапазонов: сито
                hi = math.nan
            if math.isnan(hi):                    # «поддон» — мельче самого мелкого сита
                hi = (min(finite_lo) * uf) if finite_lo and r.lo == 0 else hi
            items.append((lo, hi, float(w)))
        if any(math.isnan(hi) for _, hi, _ in items):
            return None
        bounds = sorted({b for lo, hi, _ in items for b in (lo, hi) if math.isfinite(b) and b > 0})
        if len(bounds) < 2:
            return None
        cum = [sum(w for lo, hi, w in items if math.isfinite(hi) and hi <= b + 1e-12) for b in bounds]
        notes = list(axis.notes) + ([unote] if unote else []) + ([sc] if sc else []) + [
            "фракции заданы диапазонами: ΣQ на верхней границе = сумма долей фракций мельче её"]
        return Curve(np.array(bounds), np.array(cum), "ranges", tuple(notes))
    return None


# ==================================================================== лист целиком
NAME_WORDS = ("name", "назв", "образец", "sample", "партия", "batch", "id", "имя", "проба", "record")
_DATE_RE = re.compile(r"^\s*\d{1,4}[./-]\d{1,2}[./-]\d{1,4}(\s+\d{1,2}:\d{2}(:\d{2})?)?\s*$")


_DESCRIPTOR = re.compile(
    r"накоплен\w*|накопл\w*|остат\w*|проход\w*|прошло|на\s+сите|сито|сит\w*|доля|доли|масс\w*|объ[её]м\w*|"
    r"cumulative|cum|passing|pass|retained|undersize|oversize|volume|vol|mass|density|frequency|freq\w*|"
    r"channel|chan|percent|value[s]?|мельче|крупнее|q3lg|q3|q|r|σq|Σq|δq|dq|mm|мм|мкм|µm|um|%|[(),.:;/\\\-\s*]",
    flags=re.I)


def _generic(header: str) -> bool:
    """Заголовок только описывает вид данных («Остаток на сите, %», «% Passing», «Q3, %»), а не называет пробу."""
    h = header.strip().lower().replace(" ", "")
    if h in {g.replace(" ", "") for g in GENERIC_HEADERS}:
        return True
    rest = _DESCRIPTOR.sub("", header)
    return len(re.sub(r"\W", "", rest)) < 2


def _label_left(rows, r, c) -> str:
    """Подпись строки — первый текст левее ячейки (в таблице «боком» это заголовок исходного столбца)."""
    for k in range(c - 1, -1, -1):
        v = rows[r][k] if k < len(rows[r]) else None
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _name(rows, c, r0, sheet, file: Path) -> str:
    # кандидаты — строки выше данных (пропуская числа и даты); приоритет — те, что подписаны «имя/образец»
    cands = []
    for r in range(r0 - 1, max(-1, r0 - 16), -1):
        v = rows[r][c] if c < len(rows[r]) else None
        if isinstance(v, str) and v.strip() and not _DATE_RE.match(v):
            cands.append((r, v.strip()))
    for r, v in cands:
        if _has(_label_left(rows, r, c), NAME_WORDS):
            return v
    header = cands[0][1] if cands else ""
    if header and not _generic(header) and not _has(header, SIZE_WORDS[:6]):
        return header
    if sheet and sheet.strip().lower() not in GENERIC_SHEETS and sheet != Path(file).stem:
        return sheet
    return Path(file).stem


def _values_for(rows, c, axis: Axis):
    """Числа столбца c на строках оси: (значения, сдвиг) или None.
    Сдвиг 1 — значения начинаются со второй строки оси (размеры — границы интервалов)."""
    col = _col(rows, c)
    seg = col[axis.r0:axis.r0 + axis.n]

    def num(v):
        p = _point(v)
        return None if p is None else p[0]

    vals = [num(v) for v in seg]
    if all(v is not None for v in vals):
        return vals, 0
    if axis.kind == "num" and len(vals) >= MIN_POINTS:
        if all(v is not None for v in vals[:-1]) and vals[-1] is None:
            return vals[:-1], 0
        if all(v is not None for v in vals[1:]) and vals[0] is None:
            return vals[1:], 1
    return None


def parse_oriented(rows, sheet: str, file: Path) -> list[Sample]:
    axes = find_axes(rows)
    if not axes:
        return []
    ncols = max((len(r) for r in rows), default=0)
    used: dict[int, set] = {}               # столбец → строки, уже отданные какому-то блоку

    def busy(c, rr) -> int:
        return len(used.get(c, set()) & set(rr))

    out: list[tuple[Sample, Axis]] = []
    # приоритет: подписанные как размер, диапазоны, длинные, левые
    axes.sort(key=lambda a: (not _has(a.header, SIZE_WORDS), a.kind != "range", -a.n, a.col, a.r0))
    for ax in axes:
        if busy(ax.col, ax.rows):
            continue
        # другие оси на тех же строках делят лист на «отсеки» (у каждого образца — свой столбец размеров)
        others = [b for b in axes if b is not ax and b.col != ax.col and not busy(b.col, b.rows)
                  and len(set(b.rows) & set(ax.rows)) >= 0.5 * min(b.n, ax.n)]
        left = max((b.col for b in others if b.col < ax.col and not _dist_like(rows, b, ax)), default=-1)
        right = min((b.col for b in others if b.col > ax.col and not _dist_like(rows, b, ax)), default=ncols)
        found = {"cum": [], "int": []}
        for c in range(left + 1, right):
            if c == ax.col or busy(c, ax.rows):
                continue
            got = _values_for(rows, c, ax)
            if got is None:
                continue
            vals, off = got
            header = _text_above(rows, c, ax.r0 + off) if off else _text_above(rows, c, ax.r0)
            curve = classify(ax, vals, off, header)
            if curve is None:
                continue
            group = "cum" if curve.kind in ("cum", "residue", "density") else "int"
            found[group].append((c, curve))
        chosen = found["cum"] or found["int"]
        if not chosen:
            continue
        chosen = _drop_twins(chosen)
        used.setdefault(ax.col, set()).update(ax.rows)
        for c, _ in found["cum"] + found["int"]:      # столбцы блока больше никому не достаются
            used.setdefault(c, set()).update(ax.rows)
        for c, curve in chosen:
            notes = list(curve.notes)
            if found["cum"] and found["int"]:
                notes.append("рядом есть и доли по интервалам, и накопленная — взята накопленная")
            out.append((_make_sample(rows, c, ax, curve, notes, sheet, file), ax))
    return _drop_resampled(out)


def _drop_twins(chosen):
    """«Проход» и «остаток» одной пробы дают одну кривую, а не две."""
    keep = []
    for c, curve in chosen:
        # только разные записи одного (проход ↔ остаток); две пробы с одинаковыми числами — это две пробы
        twin = next((k for k in keep if k[1].kind != curve.kind and len(k[1].cum) == len(curve.cum)
                     and np.max(np.abs(k[1].cum - curve.cum)) < 0.5), None)
        if twin is None:
            keep.append((c, curve))
        else:
            twin[1].notes = tuple(twin[1].notes) + ("в соседнем столбце та же кривая, записанная иначе "
                                                   "(например, остаток вместо прохода) — взята одна",)
    return keep


def _drop_resampled(found: list[tuple[Sample, Axis]]) -> list[Sample]:
    """Таблица-пересчёт той же кривой с более редким шагом (другая ось на том же листе, точек вдвое меньше,
    в среднем расходится не больше чем на 3 п.п.) не загружается — это не отдельный образец."""
    keep = []
    for s, ax in sorted(found, key=lambda t: -len(t[0].size_um)):
        twin = None
        for k, kax in keep:
            if kax is ax or len(s.size_um) > 0.5 * len(k.size_um):
                continue
            x = s.size_um[(s.size_um >= k.size_um[0]) & (s.size_um <= k.size_um[-1])]
            if len(x) < 0.6 * len(s.size_um) or len(x) < 3:
                continue
            diff = np.abs(np.interp(x, k.size_um, k.cum_pct) - np.interp(x, s.size_um, s.cum_pct)).mean()
            if diff <= 3.0:
                twin = k
                break
        if twin is None:
            keep.append((s, ax))
        else:
            twin.meta["import_notes"].append(
                f"на листе есть ещё таблица «{s.meta.get('column')}» ({len(s.size_um) - 1} точек) — это пересчёт "
                f"той же кривой с более редким шагом, она не загружена")
    order = {id(s): i for i, (s, _) in enumerate(found)}
    return [s for s, _ in sorted(keep, key=lambda t: order[id(t[0])])]


def _dist_like(rows, b: Axis, ax: Axis) -> bool:
    """Ось-кандидат b на самом деле — накопленная кривая для оси ax (растёт до ~100)."""
    if _has(b.header, SIZE_WORDS):
        return False
    got = _values_for(rows, b.col, ax)
    if got is None:
        return False
    return classify(ax, got[0], got[1], _text_above(rows, b.col, ax.r0 + got[1])) is not None


def _make_sample(rows, c, ax: Axis, curve: Curve, notes, sheet, file) -> Sample:
    order = np.argsort(curve.sizes, kind="stable")
    x, y = np.asarray(curve.sizes)[order], np.asarray(curve.cum)[order]
    keep = np.concatenate([[True], np.diff(x) > 0])     # повторы размеров
    x, y = x[keep], y[keep]
    name = _name(rows, c, ax.r0, sheet, file)
    s = Sample(name=name, size_um=x, cum_pct=y, file=str(file), sheet=sheet, source="table",
               meta={"column": _text_above(rows, c, ax.r0) or f"#{c + 1}", "distribution": curve.kind,
                     "import_notes": [n for n in notes if n],
                     # где лежали данные (для мастера импорта): столбец, ось, строки с числами оси
                     "src_col": c, "src_axis": ax.col,
                     "src_rows": (ax.r0 + (1 if ax.lead is not None else 0),
                                  ax.r0 + ax.n - 1 - (1 if ax.tail is not None else 0)),
                     "src_orient": "cols"})
    if ax.kind == "num" and not ax.notes and not _header_unit(ax.header)[0] and x[-1] <= 2.0:
        s.flags.append((INFO, "все размеры ≤ 2 — если это миллиметры, подпишите столбец размеров «мм» "
                              "(или задайте единицы в ручном импорте)"))
    return s


def transpose(rows) -> list[list]:
    n = max((len(r) for r in rows), default=0)
    return [[row[c] if c < len(row) else None for row in rows] for c in range(n)]


def parse_sheet(rows, sheet: str, file: Path) -> list[Sample]:
    """Лучший разбор листа: по столбцам или по строкам (таблица «боком»)."""
    rows = normalize(rows)
    by_cols = parse_oriented(rows, sheet, file)
    by_rows = parse_oriented(transpose(rows), sheet, file) if len(rows) >= 2 else []
    score = lambda ss: (len(ss), sum(len(s.size_um) for s in ss))  # noqa: E731
    best = by_rows if score(by_rows) > score(by_cols) else by_cols
    if best is by_rows and by_rows:
        for s in best:
            s.meta["import_notes"].insert(0, "таблица «боком»: размеры в строке, образцы — строки")
            s.meta["src_orient"] = "rows"
    _dedupe_names(best)
    return best


def _dedupe_names(samples):
    seen: dict[str, int] = {}
    for s in samples:
        k = seen.get(s.name, 0)
        seen[s.name] = k + 1
        if k:
            s.name = f"{s.name} ({k + 1})"


# ==================================================================== ручной импорт («рецепт»)
KINDS = {"auto": "определить автоматически", "cum": "накопленная «мельче размера» (проход, ΣQ)",
         "residue": "накопленная «крупнее размера» (остаток на сите, R)",
         "int": "доли по интервалам — доля относится к интервалу, заканчивающемуся на размере",
         "sieve": "доли по ситам — доля = остаток на сите (крупнее этого сита)",
         "density": "плотность q3 по lg x"}
UNITS = {"um": ("мкм", 1.0), "mm": ("мм", 1000.0), "nm": ("нм", 1e-3), "mesh": ("меш (ASTM E11)", None)}


def parse_recipe(rows, recipe: dict, sheet: str, file: Path) -> list[Sample]:
    """Ручной импорт: recipe = {orient: cols|rows, axis: индекс, r0, r1 (включительно), data: [индексы],
    kind: auto|cum|residue|int|sieve|density, unit: um|mm|nm|mesh, names: {индекс: имя}}."""
    rows = normalize(rows)
    if recipe.get("orient") == "rows":
        rows = transpose(rows)
    a, r0, r1 = int(recipe["axis"]), int(recipe["r0"]), int(recipe["r1"])
    unit = recipe.get("unit", "um")
    xs_raw = []
    for v in _col(rows, a)[r0:r1 + 1]:
        p = _point(v)
        if p is None:
            raise ValueError(f"в столбце размеров не число: {v!r}")
        xs_raw.append(p[0])
    if unit == "mesh":
        try:
            xs = [float(ASTM_E11_MESH[int(round(x))]) for x in xs_raw]
        except KeyError as e:
            raise ValueError(f"номер сита {e} не из стандарта ASTM E11") from e
    else:
        xs = [x * UNITS[unit][1] for x in xs_raw]
    if len(xs) < 2:
        raise ValueError("нужно хотя бы 2 размера")
    d = 1 if xs[-1] > xs[0] else -1
    if any((b - a_) * d <= 0 for a_, b in zip(xs, xs[1:])):
        raise ValueError("размеры должны идти строго по возрастанию или строго по убыванию")
    ax = Axis(a, r0, len(xs), "num", xs, d, header=f"[{UNITS[unit][0]}]")
    if unit != "um":
        ax.notes = (f"единицы размеров: {UNITS[unit][0]} → мкм",)
    kind = recipe.get("kind", "auto")
    out = []
    for c in recipe.get("data", []):
        c = int(c)
        vals = []
        for v in _col(rows, c)[r0:r1 + 1]:
            p = _point(v)
            vals.append(math.nan if p is None else p[0])
        vals = np.asarray(vals, float)
        if np.isnan(vals).any():
            raise ValueError(f"в столбце {column_letter(c)} есть пустые или нечисловые ячейки в выбранных строках")
        curve = _forced(ax, vals, kind) if kind != "auto" else classify(ax, list(vals), 0, "")
        if curve is None:
            raise ValueError(f"столбец {column_letter(c)}: не похоже ни на накопленную кривую, ни на доли "
                             f"(сумма {vals.sum():.1f}) — выберите вид данных вручную")
        notes = list(curve.notes) + ["импорт по ручной настройке (мастер импорта)"]
        s = _make_sample(rows, c, ax, curve, notes, sheet, file)
        nm = (recipe.get("names") or {}).get(str(c))
        if nm:
            s.name = nm
        out.append(s)
    _dedupe_names(out)
    return out


def _forced(ax: Axis, vals, kind) -> Curve | None:
    xs = np.asarray(ax.sizes, float)
    asc = ax.direction > 0
    x = xs if asc else xs[::-1]
    v = vals if asc else vals[::-1]
    sc = ""
    if np.nanmax(np.abs(v)) <= 1.0 + 1e-9 and kind != "density":
        v, sc = v * 100.0, "доли единицы переведены в проценты (×100)"
    notes = list(ax.notes) + ([sc] if sc else []) + ([] if asc else ["размеры шли по убыванию — таблица развёрнута"])
    if kind == "cum":
        return Curve(x, v, "cum", tuple(notes))
    if kind == "residue":
        return Curve(x, 100.0 - v, "residue", tuple(notes + ["остаток на сите пересчитан: ΣQ = 100 − R"]))
    if kind == "int":
        return Curve(x, np.cumsum(v), "int", tuple(notes + ["доля относится к интервалу, заканчивающемуся на размере"]))
    if kind == "sieve":
        return Curve(x, np.concatenate([[0.0], np.cumsum(v)[:-1]]), "sieve",
                     tuple(notes + ["доля = остаток на сите (частицы крупнее этого сита и мельче следующего)"]))
    if kind == "density":
        c = _integrate_density(x, v, "")
        return None if c is None else Curve(x, c[0], "density", tuple(notes + [c[1]]))
    return None


def column_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s
