"""Метрики гранулометрии: d10/d50/d90, span, D[4,3], D[3,2], доли по окнам, флаги, усреднение."""
from __future__ import annotations

from collections import OrderedDict

import numpy as np

from .model import ERROR, INFO, WARN, Sample

# Окна долей по умолчанию, мкм: (нижняя, верхняя); None — без границы.
DEFAULT_WINDOWS = [(None, 15), (15, 45), (15, 53), (45, 105), (53, None)]
D32_FIRST_LOWER_UM = 0.08  # нижняя граница диапазона прибора — для интервала, начинающегося с 0

OBSCURATION_MAX = 40.0
CURVE_END_TOL = 0.6
REPEAT_TOL = 2.0
TRADEOFF_RATIO = 5.0


def cum_at(s: Sample, x: float) -> float:
    """ΣQ, % при размере x (линейная интерполяция; за пределами сетки — крайнее значение)."""
    return float(np.interp(x, s.size_um, s.cum_pct))


def d_at(s: Sample, p: float) -> float:
    """Размер, при котором накопленная кривая впервые достигает p % (линейная интерполяция)."""
    x, y = s.size_um, s.cum_pct
    idx = np.nonzero(y >= p)[0]
    if len(idx) == 0:
        return float("nan")
    i = idx[0]
    if i == 0:
        return float(x[0])
    y0, y1 = y[i - 1], y[i]
    if y1 == y0:
        return float(x[i])
    return float(x[i - 1] + (p - y0) * (x[i] - x[i - 1]) / (y1 - y0))


def _intervals(s: Sample):
    lo, hi = s.size_um[:-1], s.size_um[1:]
    dq = np.diff(s.cum_pct)
    return lo, hi, dq


def d43(s: Sample) -> float:
    lo, hi, dq = _intervals(s)
    return float(np.sum((lo + hi) / 2 * dq) / np.sum(dq))


def d32(s: Sample) -> float:
    lo, hi, dq = _intervals(s)
    lo = np.where(lo <= 0, D32_FIRST_LOWER_UM, lo)
    xgm = np.sqrt(lo * hi)
    return float(np.sum(dq) / np.sum(dq / xgm))


def window_label(lo, hi) -> str:
    if lo is None:
        return f"<{hi:g}"
    if hi is None:
        return f">{lo:g}"
    return f"{lo:g}–{hi:g}"


def fraction(s: Sample, lo=None, hi=None) -> float:
    """Объёмная доля, % частиц в окне [lo, hi) мкм.

    Верхнее окно без границы (> lo) считается как 100 − ΣQ(lo): всё, что не попало
    в кривую, — крупнее последнего размера сетки (перенормировки нет).
    """
    c_lo = 0.0 if lo is None else cum_at(s, lo)
    c_hi = 100.0 if hi is None else cum_at(s, hi)
    return c_hi - c_lo


def compute(s: Sample, windows=None) -> dict:
    windows = windows or DEFAULT_WINDOWS
    d10, d50, d90 = d_at(s, 10), d_at(s, 50), d_at(s, 90)
    out = OrderedDict(
        d10=d10, d50=d50, d90=d90,
        span=(d90 - d10) / d50 if d50 else float("nan"),
        d43=d43(s), d32=d32(s),
    )
    out["fractions"] = OrderedDict((window_label(lo, hi), fraction(s, lo, hi)) for lo, hi in windows)
    return out


# ---------------------------------------------------------------- флаги качества
def check_quality(s: Sample) -> None:
    obs = s.meta.get("obscuration")
    if obs is not None:
        if obs < 0:
            s.add_flag(ERROR, f"Обскурация {obs:g} % < 0: фон записан неверно, результат ненадёжен")
        elif obs > OBSCURATION_MAX:
            s.add_flag(WARN, f"Обскурация {obs:g} % > {OBSCURATION_MAX:g} %: риск многократного рассеяния")
    end = s.cum_pct[-1]
    if abs(end - 100.0) > CURVE_END_TOL:
        s.add_flag(WARN, f"Кривая не доходит до 100 %: последняя точка {end:.1f} % (не перенормировано)")
    if np.any(np.diff(s.cum_pct) < -1e-9):
        s.add_flag(ERROR, "Накопленная кривая не монотонна: данные повреждены или сдвинуты")


def check_file(samples: list[Sample]) -> None:
    """Флаги, зависящие от всех измерений файла: разный TradeOff (сглаживание)."""
    vals = [s.meta.get("tradeoff") for s in samples]
    vals = [v for v in vals if isinstance(v, (int, float)) and v > 0]
    if len(vals) < 2:
        return
    ratio = max(vals) / min(vals)
    if ratio > TRADEOFF_RATIO:
        text = (f"TradeOff в файле различается в {ratio:.0f} раз ({min(vals):.0f}…{max(vals):.0f}): "
                "степень сглаживания разная, форму пиков сравнивать осторожно")
        for s in samples:
            s.add_flag(INFO, text)


# ---------------------------------------------------------------- усреднение повторов
def average_repeats(samples: list[Sample]) -> list[Sample]:
    """Объединяет измерения с одинаковым названием (и одинаковой сеткой) в один образец.

    Порядок образцов сохраняется. Повторы с разной сеткой не усредняются.
    """
    groups: "OrderedDict[tuple, list[Sample]]" = OrderedDict()
    for s in samples:
        groups.setdefault((s.file, s.name), []).append(s)
    out = []
    for (_, name), grp in groups.items():
        if len(grp) == 1:
            out.append(grp[0])
            continue
        same_grid = all(len(g.size_um) == len(grp[0].size_um) and np.allclose(g.size_um, grp[0].size_um)
                        for g in grp)
        if not same_grid:
            for g in grp:
                g.add_flag(WARN, "Повторы с разной сеткой размеров — не усреднены")
            out.extend(grp)
            continue
        out.append(_mean_sample(grp))
    return out


def _mean_sample(grp: list[Sample]) -> Sample:
    curves = np.vstack([g.cum_pct for g in grp])
    first = grp[0]
    meta = {"n_repeats": len(grp)}
    for key in ("obscuration", "error", "tradeoff", "ultrasonics", "pump", "d43_instrument"):
        vals = [g.meta.get(key) for g in grp if isinstance(g.meta.get(key), (int, float))]
        if vals:
            meta[key] = float(np.mean(vals))
    for key in ("date", "model", "material"):
        if key in first.meta:
            meta[key] = first.meta[key]
    avg = Sample(
        name=first.name, meas_id="+".join(g.meas_id for g in grp if g.meas_id),
        file=first.file, sheet=first.sheet, source=first.source,
        size_um=first.size_um, cum_pct=curves.mean(axis=0), meta=meta,
        members=[g.meas_id for g in grp],
    )
    for g in grp:
        for f in g.flags:
            avg.add_flag(*f)
    spread = float(np.max(curves.max(axis=0) - curves.min(axis=0)))
    avg.meta["repeat_spread_pp"] = spread
    if spread > REPEAT_TOL:
        avg.add_flag(WARN, f"Повторы расходятся до {spread:.1f} п.п. (> {REPEAT_TOL:g})")
    return avg
