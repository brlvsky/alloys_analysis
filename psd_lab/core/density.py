"""М7. Калькулятор плотности составов: ат.% ↔ мас.%, правило смесей 1/ρ = Σ wᵢ/ρᵢ.

Атомные массы — общая таблица core/elements.py (IUPAC/CIAAW, с версии 1.1); плотности элементов — CRC Handbook of Chemistry
and Physics (Haynes, 95-е изд.), при комнатной температуре; значения взяты из базы пакета mendeleev 1.3
и сверены с пакетом periodictable 2.1 (CRC, 80-е изд.): расхождение ≤ 1 % для всех элементов,
кроме C (графит 2,2–2,26), Ta, Mn, V и Mo (1–1,7 %); подробности — NOTES.md. Y₂O₃: 5,01 г/см³
(в разных источниках 5,01–5,03; при добавке ≤ 1,5 мас.% это меньше 0,01 % итоговой плотности).
Соединения для калькулятора шихты (1.1): CeO₂ 7,215 и TiB₂ 4,52 (Wikipedia), Nb₂O₅ 4,60, SiC 3,21
(3,16–3,22 в зависимости от политипа), Al₂O₃ 3,98 (3,95–3,99), TiC 4,93 — проверить по первоисточнику.
Для интерметаллидов (γ-TiAl) правило смесей ошибается на несколько процентов — если есть
измеренная плотность, используется она.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# плотности, г/см³ (источники в докстринге модуля); атомные массы — общие, core/elements.py
DENSITY = {
    "Ti": 4.506, "Al": 2.70, "Nb": 8.57, "Mo": 10.2, "B": 2.34, "Si": 2.3296, "C": 2.2, "Cr": 7.15,
    "V": 6.0, "Fe": 7.87, "Zr": 6.52, "Hf": 13.3, "Ta": 16.4, "W": 19.3, "Y": 4.47, "Ni": 8.9,
    "Mn": 7.3, "Sn": 7.287, "Co": 8.86, "Cu": 8.96, "Ce": 6.77, "Mg": 1.74, "La": 6.15,
}
# соединения (добавки), г/см³ — справочные значения; при спорных — проверить по первоисточнику (NOTES.md)
COMPOUND_DENSITY = {
    "Y2O3": 5.01, "CeO2": 7.215, "TiB2": 4.52, "TiC": 4.93, "SiC": 3.21, "Al2O3": 3.98, "Nb2O5": 4.60,
}


def component_density(name: str) -> float | None:
    """Плотность элемента или соединения, г/см³; None — нет справочного значения."""
    from .elements import normalize_name

    n = normalize_name(name)
    return DENSITY.get(n) or COMPOUND_DENSITY.get(n)


def _elements_table():
    """Совместимость с версией 1.0: {компонент: (молярная масса, плотность)}."""
    from .elements import ATOMIC_MASS, molar_mass

    out = {el: (ATOMIC_MASS[el], rho) for el, rho in DENSITY.items() if el in ATOMIC_MASS}
    out.update({c: (molar_mass(c), rho) for c, rho in COMPOUND_DENSITY.items()})
    return out


ELEMENTS = _elements_table()
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
    """«Ti-43.5Al-4Nb-1Mo-0.1B» → {'Ti': 51.4, 'Al': 43.5, …} (основа — остаток до 100) или все доли
    («50Ti-44Al-…»). Общий разбор состава — core/charge.parse_composition."""
    from .charge import ChargeError, parse_composition

    try:
        comp = parse_composition(text)
    except ChargeError as e:
        raise ValueError(str(e)) from e
    for c in comp.values:
        if component_density(c) is None:
            raise ValueError(f"нет справочной плотности для «{c}»")
    return comp.values


def at_to_wt(at: dict[str, float], overrides: dict | None = None) -> dict[str, float]:
    from .charge import to_wt
    from .elements import masses

    return to_wt(at, masses(overrides))


def wt_to_at(wt: dict[str, float], overrides: dict | None = None) -> dict[str, float]:
    from .charge import to_at
    from .elements import masses

    return to_at(wt, masses(overrides))


def mixture_density(wt: dict[str, float]) -> float:
    """Правило смесей: 1/ρ = Σ wᵢ/ρᵢ (wᵢ — массовые доли)."""
    s = sum(wt.values())
    return 1.0 / sum((w / s) / component_density(e) for e, w in wt.items())


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
