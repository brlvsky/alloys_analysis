"""М6. Оценка плотности упаковки слоя для бимодальных порошков.

Линейная модель упаковки бинарных смесей (Westman–Hugill; Yu A.B., Standish N.,
Ind. Eng. Chem. Res. 1991, 30, 1372–1385). Удельный объём V = 1/φ:

    V₁ᵀ = V₁·X₁ + V₂·[1 − f(r)]·X₂            (каркас из крупных, мелкие в пустотах)
    V₂ᵀ = [V₁ − (V₁ − 1)·g(r)]·X₁ + V₂·X₂      (каркас из мелких, крупные «вкраплены»)
    V   = max(V₁ᵀ, V₂ᵀ)

r = d_мелк / d_крупн ≤ 1; X — объёмные доли; V₁ = V₂ = 1/φ₀ (монофракции).
f(r) = (1 − r)^3,3 + 2,8·r·(1 − r)^2,7;  g(r) = (1 − r)^2 + 0,4·r·(1 − r)^3,7
(коэффициенты — проверить по первоисточнику). Пределы: r → 1 — идеальное смешение (φ = φ₀);
r → 0 — классический предел Фёрнаса, φ_max = φ₀ + (1 − φ₀)·φ₀.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ASSUMPTIONS = ("сухие сферы без когезии; каждая популяция упакована как монофракция с плотностью φ₀; "
               "мелочь < ~20 мкм реально пакуется хуже из-за когезии — это ВЕРХНЯЯ оценка плотности слоя.")
SOURCE = ("линейная модель упаковки бинарных смесей: Yu A.B., Standish N., Ind. Eng. Chem. Res. 1991, 30, "
          "1372–1385 (модель Westman–Hugill); коэффициенты f(r), g(r) — проверить по первоисточнику.")


def f_r(r):
    r = np.asarray(r, float)
    return (1 - r) ** 3.3 + 2.8 * r * (1 - r) ** 2.7


def g_r(r):
    r = np.asarray(r, float)
    return (1 - r) ** 2 + 0.4 * r * (1 - r) ** 3.7


def packing_fraction(x_fine, r, phi0=0.60):
    """Плотность упаковки φ смеси при объёмной доле мелкой фракции x_fine и отношении размеров r."""
    x2 = np.asarray(x_fine, float)
    x1 = 1 - x2
    v = 1.0 / phi0
    v1t = v * x1 + v * (1 - f_r(r)) * x2
    v2t = (v - (v - 1) * g_r(r)) * x1 + v * x2
    return 1.0 / np.maximum(v1t, v2t)


def optimum(r, phi0=0.60, n=2001):
    """(доля мелкой фракции, φ) в максимуме плотности упаковки."""
    x = np.linspace(0, 1, n)
    phi = packing_fraction(x, r, phi0)
    i = int(np.argmax(phi))
    return float(x[i]), float(phi[i])


@dataclass
class PackingEstimate:
    applicable: bool
    reason: str = ""
    d_fine: float | None = None
    d_coarse: float | None = None
    r: float | None = None
    x_fine: float | None = None          # доля мелкой популяции среди двух основных, 0…1
    phi: float | None = None
    x_opt: float | None = None
    phi_opt: float | None = None
    phi0: float = 0.60


def estimate(res, phi0: float = 0.60) -> PackingEstimate:
    """Оценка по результату разложения М2 (мелкая и крупная популяции, размеры — по модам)."""
    main = res.main_populations
    if len(main) < 2:
        return PackingEstimate(False, "распределение одномодальное — модель бинарной смеси неприменима", phi0=phi0)
    fine, coarse = main[0], main[-1]
    wsum = fine.weight_pct + coarse.weight_pct
    x = fine.weight_pct / wsum
    r = fine.mode_um / coarse.mode_um
    xo, po = optimum(r, phi0)
    return PackingEstimate(True, "", fine.mode_um, coarse.mode_um, r, x, float(packing_fraction(x, r, phi0)),
                           xo, po, phi0)
