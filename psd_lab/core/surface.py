"""М5. Удельная поверхность и вклад фракций в поверхность (риск набора кислорода).

    SSA [м²/г] = 6 / (ρ [г/см³] · D[3,2] [мкм])

Вклад интервала в поверхность ∝ ΔQ / x_gm (x_gm — среднее геометрическое границ интервала;
для интервала от 0 нижняя граница 0,08 мкм — как в D[3,2]).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .metrics import D32_FIRST_LOWER_UM, d32, window_label
from .model import Sample

ASSUMPTIONS = ("Допущения: частицы — гладкие сферы; это нижняя оценка удельной поверхности (реальные частицы "
               "шероховатые и несферические — поверхность больше). Набор кислорода зависит от поверхности, "
               "поэтому мелкая фракция особенно опасна для TiAl. Реальное содержание кислорода — только по "
               "химанализу (таблица chem в базе данных).")


def ssa_m2_g(s: Sample, rho_g_cm3: float = 4.0) -> float:
    return 6.0 / (rho_g_cm3 * d32(s))


def partition(windows) -> list[tuple]:
    """Непересекающиеся интервалы из границ окон: <15, 15–45, 45–53, 53–105, >105 и т.п."""
    edges = sorted({v for w in windows for v in w if v is not None})
    bounds = [None] + edges + [None]
    return list(zip(bounds[:-1], bounds[1:]))


@dataclass
class ShareRow:
    label: str
    lo: float | None
    hi: float | None
    volume_pct: float
    surface_pct: float


def _refined(s: Sample, edges):
    """Сетка с вставленными границами окон (ΣQ на границах — интерполяцией)."""
    x = np.union1d(s.size_um, [e for e in edges if s.size_um[0] < e < s.size_um[-1]])
    return x, np.interp(x, s.size_um, s.cum_pct)


def shares(s: Sample, windows) -> list[ShareRow]:
    """Доля объёма и доля поверхности по непересекающимся интервалам размеров.

    Доли считаются от измеренной части кривой (что не попало в кривую, — крупнее сетки
    и на поверхность почти не влияет).
    """
    parts = partition(windows)
    x, c = _refined(s, [v for p in parts for v in p if v is not None])
    lo_e, hi_e = x[:-1], x[1:]
    dq = np.diff(c)
    xgm = np.sqrt(np.where(lo_e <= 0, D32_FIRST_LOWER_UM, lo_e) * hi_e)
    surf = dq / xgm
    total_v, total_s = dq.sum(), surf.sum()
    rows = []
    for lo, hi in parts:
        sel = np.ones_like(lo_e, bool)
        if lo is not None:
            sel &= lo_e >= lo - 1e-9
        if hi is not None:
            sel &= hi_e <= hi + 1e-9
        rows.append(ShareRow(window_label(lo, hi), lo, hi, float(100 * dq[sel].sum() / total_v),
                             float(100 * surf[sel].sum() / total_s)))
    return rows


def fine_shares(s: Sample, fine_um: float = 15.0) -> tuple[float, float]:
    """(% объёма, % поверхности) у частиц мельче fine_um."""
    r = shares(s, [[None, fine_um]])[0]
    return r.volume_pct, r.surface_pct


def headline(s: Sample, fine_um: float = 15.0) -> str:
    v, a = fine_shares(s, fine_um)
    f = lambda z: f"{z:.1f}".replace(".", ",")  # noqa: E731
    return f"Фракция < {fine_um:g} мкм — {f(v)} % объёма, но {f(a)} % поверхности."
