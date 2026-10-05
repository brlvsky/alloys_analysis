"""М9. Кинетика помола: d10/d50/d90 и доли от времени обработки.

Подгонка d(t) = d∞ + (d0 − d∞)·e^(−kt) — только если точек ≥ 4 и тренд монотонный;
иначе — только точки и предупреждение.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

OLD_DATA_NOTE = "данные 6/8/10 ч — из старого шаблона «Расчет.xlsx» (2017–2019), материал неизвестен."
GROWTH_HINT = ("рост размера при длительной обработке: возможны агломерация или холодная сварка частиц; "
               "проверить СЭМ.")


def time_from_name(name: str) -> float | None:
    """«6ч», «10 h», «30 мин», «помол 2,5ч» → часы."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ч|час|h|hr|мин|min)\b", name, flags=re.IGNORECASE) or \
        re.search(r"(\d+(?:[.,]\d+)?)\s*(ч|h)$", name, flags=re.IGNORECASE)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return v / 60 if m.group(2).lower() in ("мин", "min") else v


def exp_model(t, d_inf, d0, k):
    return d_inf + (d0 - d_inf) * np.exp(-k * np.asarray(t, float))


@dataclass
class Fit:
    ok: bool
    params: tuple | None = None       # d∞, d0, k
    message: str = ""


def monotonic(y) -> bool:
    d = np.diff(np.asarray(y, float))
    return bool(np.all(d < 0) or np.all(d > 0))


def fit(t, y) -> Fit:
    from scipy.optimize import curve_fit

    t, y = np.asarray(t, float), np.asarray(y, float)
    if len(t) < 4:
        return Fit(False, message=f"точек {len(t)} (< 4) — экспонента не подгоняется, показаны только точки")
    if not monotonic(y[np.argsort(t)]):
        return Fit(False, message="тренд немонотонный — экспонента не подгоняется, показаны только точки")
    try:
        p, _ = curve_fit(exp_model, t, y, p0=(y[-1], y[0], 1 / max(np.ptp(t), 1e-9)), maxfev=20000)
    except Exception as e:  # noqa: BLE001
        return Fit(False, message=f"подгонка не сошлась ({e})")
    return Fit(True, tuple(float(v) for v in p), "d(t) = d∞ + (d0 − d∞)·e^(−kt)")


def growth_after_minimum(t, y, tol=0.02) -> bool:
    """Размер после минимума вырос больше чем на tol (относительно)."""
    order = np.argsort(t)
    y = np.asarray(y, float)[order]
    i = int(np.argmin(y))
    return i < len(y) - 1 and y[i + 1:].max() > y[i] * (1 + tol)


@dataclass
class KineticsResult:
    times: list
    names: list
    d: dict = field(default_factory=dict)        # «d10» → [..]
    fits: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    hints: list = field(default_factory=list)


def analyse(samples_times: list[tuple], windows=None) -> KineticsResult:
    """samples_times: [(Sample, часы)] — образцы с назначенным временем."""
    from .metrics import compute

    pts = sorted(((t, s) for s, t in samples_times if t is not None), key=lambda p: p[0])
    res = KineticsResult([p[0] for p in pts], [p[1].name for p in pts])
    if not pts:
        res.warnings.append("нет образцов с назначенным временем обработки")
        return res
    ms = [compute(s, windows) for _, s in pts]
    for k in ("d10", "d50", "d90"):
        res.d[k] = [m[k] for m in ms]
    for lab in ms[0]["fractions"]:
        res.d[f"frac:{lab}"] = [m["fractions"][lab] for m in ms]
    for k in ("d10", "d50", "d90"):
        res.fits[k] = fit(res.times, res.d[k])
    msgs = {f.message for f in res.fits.values() if not f.ok}
    res.warnings += sorted(msgs)
    if any(growth_after_minimum(res.times, res.d[k]) for k in ("d50", "d90")):
        res.hints.append(GROWTH_HINT)
    return res
