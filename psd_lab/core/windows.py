"""М3 + М4. Окна гранулометрии для СЛС / СЭЛС и выход годного после рассева.

Только фактические доли — без автоматического «вердикта» о технологии.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .metrics import cum_at, d_at, window_label
from .model import Sample

TECH_NOTE = ("Справка (проверить по источникам): γ-TiAl при СЛС без высокого подогрева склонен к "
             "растрескиванию; промышленно его печатают электронным лучом с подогревом (например, лопатки ТНД "
             "из Ti-48Al-2Cr-2Nb). ТЗ проекта допускает СЭЛС.")
REQ_NOTE = "Требования — типовые ориентиры для СЛС, уточнить под конкретную машину."
SIEVE_NOTE = ("Кривая «после рассева» — модель идеального рассева: распределение обрезано по окну и "
              "перенормировано на 100 %. Это единственное место программы, где перенормировка допустима.")


def frac(s: Sample, lo, hi) -> float:
    """Доля объёма, %, в окне [lo, hi); верхнее окно без границы — 100 − ΣQ(lo)."""
    a = 0.0 if lo is None else cum_at(s, lo)
    b = 100.0 if hi is None else cum_at(s, hi)
    return b - a


# ---------------------------------------------------------------- М3: составная полоса
@dataclass
class Segment:
    name: str          # «мельче», «окно СЛС», «между», «окно СЭЛС», «СЛС и СЭЛС», «крупнее»
    label: str         # диапазон: «<15», «15–45», «>105»
    lo: float | None
    hi: float | None
    pct: float
    role: str          # fine / sls / both / gap / ebm / coarse


def segments(s: Sample, sls, ebm) -> list[Segment]:
    """Полоса «<15 | окно СЛС | между | окно СЭЛС | крупнее». Перекрытие окон — отдельный сегмент."""
    edges = sorted({sls[0], sls[1], ebm[0], ebm[1]})
    bounds = [None] + edges + [None]
    out = []
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        mid = (lo or 0) if hi is None else ((lo or 0) + hi) / 2
        in_s = (lo is not None and hi is not None) and sls[0] <= mid < sls[1]
        in_e = (lo is not None and hi is not None) and ebm[0] <= mid < ebm[1]
        if in_s and in_e:
            role, name = "both", "СЛС и СЭЛС"
        elif in_s:
            role, name = "sls", "окно СЛС"
        elif in_e:
            role, name = "ebm", "окно СЭЛС"
        elif lo is None:
            role, name = "fine", "мельче"
        elif hi is None:
            role, name = "coarse", "крупнее"
        else:
            role, name = "gap", "между"
        out.append(Segment(name, window_label(lo, hi), lo, hi, frac(s, lo, hi), role))
    return out


def fmt_pct(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def facts_text(s: Sample, sls, ebm) -> str:
    """Фактическая фраза без вердикта (десятичная запятая)."""
    return (f"В окне СЛС {sls[0]:g}–{sls[1]:g} мкм — {fmt_pct(frac(s, *sls))} %, "
            f"в окне СЭЛС {ebm[0]:g}–{ebm[1]:g} мкм — {fmt_pct(frac(s, *ebm))} %. "
            f"Мельче {sls[0]:g} мкм — {fmt_pct(frac(s, None, sls[0]))} %, "
            f"крупнее {ebm[1]:g} мкм — {fmt_pct(frac(s, ebm[1], None))} %.")


# ---------------------------------------------------------------- М4: выход годного
@dataclass
class SieveResult:
    lo: float
    hi: float
    yield_pct: float
    fines_pct: float
    coarse_pct: float
    sieved: Sample          # модель после идеального рассева (перенормирована, подписано)

    def grams_per_kg(self) -> float:
        return 10.0 * self.yield_pct


def sieve(s: Sample, lo: float, hi: float) -> SieveResult:
    y = frac(s, lo, hi)
    fines = frac(s, None, lo)
    coarse = frac(s, hi, None)
    x = s.size_um
    inner = x[(x > lo) & (x < hi)]
    grid = np.concatenate([[lo], inner, [hi]])
    c = np.array([cum_at(s, v) for v in grid])
    c = (c - c[0]) / (c[-1] - c[0]) * 100 if c[-1] > c[0] else np.zeros_like(c)
    grid = np.concatenate([[0.0], grid])
    c = np.concatenate([[0.0], c])
    sv = Sample(name=f"{s.name} (после рассева {lo:g}–{hi:g})", size_um=grid, cum_pct=c, file=s.file,
                sheet=s.sheet, source=s.source, meta={"model": "идеальный рассев (перенормировано)"})
    return SieveResult(lo, hi, y, fines, coarse, sv)


DEFAULT_REQUIREMENTS = {"d10_min": 15.0, "d50_min": 25.0, "d50_max": 35.0, "d90_max": 53.0}


@dataclass
class ReqRow:
    name: str
    requirement: str
    value: float
    ok: bool


def requirements_check(s: Sample, req: dict | None = None) -> list[ReqRow]:
    r = {**DEFAULT_REQUIREMENTS, **(req or {})}
    d10, d50, d90 = d_at(s, 10), d_at(s, 50), d_at(s, 90)
    fines = frac(s, None, r["d10_min"])
    return [
        ReqRow("d10, мкм", f"≥ {r['d10_min']:g}", d10, d10 >= r["d10_min"]),
        ReqRow("d50, мкм", f"{r['d50_min']:g}–{r['d50_max']:g}", d50, r["d50_min"] <= d50 <= r["d50_max"]),
        ReqRow("d90, мкм", f"≤ {r['d90_max']:g}", d90, d90 <= r["d90_max"]),
        # d10 ≥ X равносильно «мельче X мкм не больше 10 %» — новой константы не вводим
        ReqRow(f"Мельче {r['d10_min']:g} мкм, %", "≤ 10 (то же, что d10 ≥ "
               f"{r['d10_min']:g})", fines, fines <= 10.0 + 1e-9),
    ]


def population_windows(pop_list, windows) -> list[tuple[str, list[float]]]:
    """Какая доля каждой популяции (в % от неё самой) попадает в каждое окно."""
    from .deconv import window_share

    out = []
    for p in pop_list:
        shares = []
        for lo, hi in windows:
            shares.append(sum(c.weight_pct * window_share(c, lo, hi) / 100 for c in p.components)
                          / p.weight_pct * 100)
        out.append((p.kind, shares))
    return out


