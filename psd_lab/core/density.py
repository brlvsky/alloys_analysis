"""М7. Калькулятор плотности составов: ат.% ↔ мас.%, правило смесей 1/ρ = Σ wᵢ/ρᵢ.

Плотности и атомные массы элементов — справочные (CRC Handbook of Chemistry and Physics, IUPAC 2021;
проверить по первоисточнику при необходимости). Для интерметаллидов (γ-TiAl) правило смесей ошибается
на несколько процентов — если есть измеренная плотность, используется она.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# элемент: (атомная/молярная масса, г/моль; плотность при 20 °C, г/см³)
ELEMENTS = {
    "Ti": (47.867, 4.506), "Al": (26.982, 2.699), "Nb": (92.906, 8.57), "Mo": (95.95, 10.28),
    "B": (10.81, 2.34), "Si": (28.085, 2.329), "C": (12.011, 2.26), "Cr": (51.996, 7.19),
    "V": (50.942, 6.0), "Fe": (55.845, 7.874), "Zr": (91.224, 6.52), "Hf": (178.49, 13.31),
    "Ta": (180.948, 16.69), "W": (183.84, 19.25), "Y": (88.906, 4.47), "Ni": (58.693, 8.908),
    "Mn": (54.938, 7.21), "Sn": (118.71, 7.287), "Y2O3": (225.81, 5.01),
}
TI64_DENSITY = 4.43            # г/см³, Ti-6Al-4V (ТЗ проекта)
TARGET = (-15.0, -10.0)        # цель ТЗ: на 10–15 % легче Ti6Al4V
ADDITIVES = ("Si", "C", "Y2O3")
PRESETS = {
    "TNM-B1 (номинал, ат.%)": ("Ti-43.5Al-4Nb-1Mo-0.1B", "at"),
    "Ti-48Al-2Cr-2Nb (ат.%)": ("Ti-48Al-2Cr-2Nb", "at"),
    "Ti6Al4V (мас.%)": ("Ti-6Al-4V", "wt"),
}
ASSUMPTIONS = ("для интерметаллидов (γ-TiAl) правило смесей ошибается на несколько процентов (не учитывает "
               "объём смешения и пористость); если есть измеренная плотность — используется она. Реальные "
               "γ-TiAl ≈ 3,9–4,2 г/см³. Точный состав TANMB неизвестен — взять у руководителя.")


def parse_formula(text: str) -> dict[str, float]:
    """«Ti-43.5Al-4Nb-1Mo-0.1B» → {'Ti': 51.4, 'Al': 43.5, …}; первый элемент — основа (остаток до 100)."""
    parts = [p for p in re.split(r"[-–\s]+", text.strip()) if p]
    if not parts:
        raise ValueError("пустой состав")
    base = parts[0]
    if base not in ELEMENTS:
        raise ValueError(f"неизвестный элемент «{base}»")
    comp = {}
    for p in parts[1:]:
        m = re.fullmatch(r"(\d+(?:[.,]\d+)?)([A-Z][a-z]?(?:2O3)?)", p)
        if not m:
            raise ValueError(f"не понял «{p}»: ожидается число и элемент, например 43.5Al")
        el = m.group(2)
        if el not in ELEMENTS:
            raise ValueError(f"неизвестный элемент «{el}»")
        comp[el] = comp.get(el, 0) + float(m.group(1).replace(",", "."))
    rest = 100 - sum(comp.values())
    if rest <= 0:
        raise ValueError("сумма легирующих ≥ 100 %")
    return {base: rest, **comp}


def at_to_wt(at: dict[str, float]) -> dict[str, float]:
    m = {e: x * ELEMENTS[e][0] for e, x in at.items()}
    s = sum(m.values())
    return {e: 100 * v / s for e, v in m.items()}


def wt_to_at(wt: dict[str, float]) -> dict[str, float]:
    n = {e: w / ELEMENTS[e][0] for e, w in wt.items()}
    s = sum(n.values())
    return {e: 100 * v / s for e, v in n.items()}


def mixture_density(wt: dict[str, float]) -> float:
    """Правило смесей: 1/ρ = Σ wᵢ/ρᵢ (wᵢ — массовые доли)."""
    s = sum(wt.values())
    return 1.0 / sum((w / s) / ELEMENTS[e][1] for e, w in wt.items())


@dataclass
class DensityResult:
    at: dict = field(default_factory=dict)
    wt: dict = field(default_factory=dict)
    rho_estimate: float = 0.0
    rho_measured: float | None = None

    @property
    def rho(self) -> float:
        return self.rho_measured or self.rho_estimate

    @property
    def delta_pct(self) -> float:
        return 100 * (self.rho - TI64_DENSITY) / TI64_DENSITY

    @property
    def in_target(self) -> bool:
        return TARGET[0] <= self.delta_pct <= TARGET[1]


def calculate(formula: str, basis: str = "at", additives: dict | None = None,
              measured: float | None = None) -> DensityResult:
    """Состав (ат.% или мас.%) + добавки в мас.% поверх сплава → плотность и сравнение с Ti6Al4V."""
    comp = parse_formula(formula)
    wt = at_to_wt(comp) if basis == "at" else {e: v * 100 / sum(comp.values()) for e, v in comp.items()}
    add = {k: float(v) for k, v in (additives or {}).items() if v}
    total_add = sum(add.values())
    if total_add >= 100:
        raise ValueError("добавки ≥ 100 мас.%")
    if add:
        wt = {e: w * (100 - total_add) / 100 for e, w in wt.items()}
        for k, v in add.items():
            wt[k] = wt.get(k, 0) + v
    at = wt_to_at(wt)
    return DensityResult(at, wt, mixture_density(wt), measured or None)
