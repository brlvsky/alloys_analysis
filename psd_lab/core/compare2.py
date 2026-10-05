"""Сравнение двух образцов «до и после» (например, порошок без добавки → с добавкой, до → после обработки).

Накопленные кривые обоих образцов переводятся на общую сетку размеров (объединение сеток, линейная
интерполяция ΣQ — так же, как при расчёте dXX), разность ΔΣQ(x) = ΣQ_B(x) − ΣQ_A(x):
ΔΣQ > 0 — у образца B больше частиц мельче x (B «мельче» в этой области).
Разности метрик — B − A. Вывод только фактический, без оценки «лучше/хуже».
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .metrics import REPEAT_TOL, compute, cum_at
from .model import ERROR, WARN, Sample

ASSUMPTIONS = (f"кривые сравниваются как есть, без обрезки и перенормировки; общая сетка — объединение сеток "
               f"двух образцов, ΣQ между точками — линейная интерполяция. Расхождение меньше ~{REPEAT_TOL:g} п.п. "
               f"сопоставимо с допустимым разбросом повторных измерений (порог флага качества), поэтому его "
               f"не стоит считать реальным различием порошков.")


@dataclass
class MetricDiff:
    name: str
    unit: str
    a: float
    b: float

    @property
    def delta(self) -> float:
        return self.b - self.a

    @property
    def rel_pct(self) -> float | None:
        """Относительное изменение, % (только для размеров; для долей — п.п. в delta)."""
        if self.unit != "мкм" or not self.a:
            return None
        return 100 * (self.b - self.a) / self.a


@dataclass
class PairDiff:
    a: Sample
    b: Sample
    grid: np.ndarray
    cum_a: np.ndarray
    cum_b: np.ndarray
    metrics: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def delta(self) -> np.ndarray:
        return self.cum_b - self.cum_a

    @property
    def max_delta(self) -> tuple[float, float]:
        """(размер, ΔΣQ) — где кривые расходятся сильнее всего."""
        i = int(np.argmax(np.abs(self.delta)))
        return float(self.grid[i]), float(self.delta[i])


def compare(a: Sample, b: Sample, windows=None) -> PairDiff:
    grid = np.union1d(a.size_um[a.size_um > 0], b.size_um[b.size_um > 0])
    ca = np.array([cum_at(a, x) for x in grid])
    cb = np.array([cum_at(b, x) for x in grid])
    ma, mb = compute(a, windows), compute(b, windows)
    metrics = [MetricDiff(k, "мкм", ma[k], mb[k]) for k in ("d10", "d50", "d90")]
    metrics.append(MetricDiff("span", "", ma["span"], mb["span"]))
    metrics += [MetricDiff("D[4,3]", "мкм", ma["d43"], mb["d43"]), MetricDiff("D[3,2]", "мкм", ma["d32"], mb["d32"])]
    metrics += [MetricDiff(f"{lab} мкм", "%", ma["fractions"][lab], mb["fractions"][lab]) for lab in ma["fractions"]]
    d = PairDiff(a, b, grid, ca, cb, metrics)
    for s in (a, b):
        bad = [f for f in s.flags if f[0] in (ERROR, WARN)]
        if bad:
            d.warnings.append(f"у образца {s.label} есть замечания по качеству ({bad[0][1]}) — "
                              f"разницу оценивайте осторожно")
    return d


def _n(v, nd=2) -> str:
    return "—" if v is None or v != v else f"{v:.{nd}f}".replace(".", ",").replace("-", "−")


def _signed(v, nd=1) -> str:
    if v is None or v != v:
        return "—"
    return ("+" if v > 0 else "") + _n(v, nd)


def summary_text(d: PairDiff) -> str:
    """Факты одной строкой: «d50: 19,64 → 12,31 мкм (−37,3 %); …; наибольшее расхождение кривых …»."""
    parts = []
    for m in d.metrics:
        if m.name in ("d10", "d50", "d90"):
            parts.append(f"{m.name}: {_n(m.a)} → {_n(m.b)} мкм ({_signed(m.rel_pct)} %)")
    fine = next((m for m in d.metrics if m.unit == "%"), None)
    if fine is not None:
        parts.append(f"доля {fine.name}: {_n(fine.a, 1)} → {_n(fine.b, 1)} % ({_signed(fine.delta)} п.п.)")
    x, dv = d.max_delta
    where = "мельче" if dv > 0 else "крупнее"
    parts.append(f"наибольшее расхождение кривых — {_signed(dv)} п.п. при {_n(x, 1 if x < 100 else 0)} мкм "
                 f"(в этой области {d.b.label} {where}, чем {d.a.label})")
    if abs(dv) < REPEAT_TOL:
        parts.append(f"это меньше {REPEAT_TOL:g} п.п. — в пределах разброса повторов")
    return "; ".join(parts) + "."


def table_rows(d: PairDiff) -> list[list[str]]:
    """Строки таблицы: показатель | A | B | B − A (для долей — п.п.) | изменение, %."""
    rows = []
    for m in d.metrics:
        nd = 1 if m.unit == "%" else 2
        unit = f", {m.unit}" if m.unit else ""
        rel = _signed(m.rel_pct) if m.rel_pct is not None else "—"   # для долей разность уже в п.п.
        rows.append([m.name + unit, _n(m.a, nd), _n(m.b, nd), _signed(m.delta, nd), rel])
    return rows
