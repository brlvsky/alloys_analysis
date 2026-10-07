"""Атомные массы и химические формулы — единые для всей программы (калькулятор шихты, плотность М7).

Атомные массы — стандартные атомные веса IUPAC/CIAAW (сокращённые / конвенциональные значения); опорные
значения взяты из ТЗ 1.1 (Ti 47,867; Al 26,9815385; Nb 92,90637; Mo 95,95; B 10,81; C 12,011; Si 28,085;
Ce 140,116; O 15,999; Y 88,90584) — источник и замечания в NOTES.md. Массы можно переопределить
(например, чтобы воспроизвести ручной расчёт с округлёнными массами): параметр overrides.
"""
from __future__ import annotations

import re

ATOMIC_MASS: dict[str, float] = {
    "H": 1.008, "B": 10.81, "C": 12.011, "N": 14.007, "O": 15.999, "Mg": 24.305, "Al": 26.9815385,
    "Si": 28.085, "Ca": 40.078, "Ti": 47.867, "V": 50.9415, "Cr": 51.9961, "Mn": 54.938044, "Fe": 55.845,
    "Co": 58.933194, "Ni": 58.6934, "Cu": 63.546, "Y": 88.90584, "Zr": 91.224, "Nb": 92.90637, "Mo": 95.95,
    "Sn": 118.71, "La": 138.90547, "Ce": 140.116, "Hf": 178.49, "Ta": 180.94788, "W": 183.84,
}

_TOKEN = re.compile(r"([A-Z][a-z]?)|(\()|(\))|(\d+(?:[.,]\d+)?)")


def masses(overrides: dict | None = None) -> dict[str, float]:
    """Таблица атомных масс с учётом переопределений пользователя."""
    m = dict(ATOMIC_MASS)
    for k, v in (overrides or {}).items():
        if k not in m:
            raise ValueError(f"переопределение массы: неизвестный элемент «{k}»")
        if not v or float(v) <= 0:
            raise ValueError(f"переопределение массы {k}: масса должна быть больше 0")
        m[k] = float(v)
    return m


def parse_formula(formula: str) -> dict[str, float]:
    """Химическая формула → число атомов каждого элемента: «CeO2» → {Ce: 1, O: 2}; «Ca(OH)2» → {Ca: 1, O: 2, H: 2}.
    Неизвестный элемент или ошибка записи — ValueError с понятным текстом."""
    f = formula.strip()
    if not f:
        raise ValueError("пустая формула")
    pos = 0
    stack: list[dict[str, float]] = [{}]
    last: dict[str, float] | str | None = None
    while pos < len(f):
        m = _TOKEN.match(f, pos)
        if not m:
            raise ValueError(f"не понял формулу «{formula}» (символ «{f[pos]}»)")
        el, opn, cls, num = m.groups()
        pos = m.end()
        if el:
            if el not in ATOMIC_MASS:
                raise ValueError(f"неизвестный элемент «{el}» в «{formula}»")
            stack[-1][el] = stack[-1].get(el, 0.0) + 1.0
            last = el
        elif opn:
            stack.append({})
            last = None
        elif cls:
            if len(stack) == 1:
                raise ValueError(f"лишняя «)» в «{formula}»")
            grp = stack.pop()
            for k, v in grp.items():
                stack[-1][k] = stack[-1].get(k, 0.0) + v
            last = grp
        else:
            n = float(num.replace(",", "."))
            if last is None:
                raise ValueError(f"число без элемента в «{formula}»")
            if isinstance(last, str):
                stack[-1][last] += n - 1.0
            else:
                for k, v in last.items():
                    stack[-1][k] += v * (n - 1.0)
            last = None
    if len(stack) != 1:
        raise ValueError(f"не закрыта «(» в «{formula}»")
    return stack[0]


def is_element(name: str) -> bool:
    return name in ATOMIC_MASS


def molar_mass(formula: str, overrides: dict | None = None) -> float:
    """Молярная масса элемента или соединения, г/моль."""
    m = masses(overrides)
    return sum(n * m[el] for el, n in parse_formula(formula).items())


def normalize_name(name: str) -> str:
    """Подстрочные цифры и пробелы: «CeO₂» → «CeO2»."""
    sub = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
    return name.translate(sub).replace(" ", "")
