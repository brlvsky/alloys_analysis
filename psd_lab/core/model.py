"""Модель данных: один образец (одно измерение или среднее нескольких повторов)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import numpy as np

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"
LEVEL_NAMES = {ERROR: "ОШИБКА", WARN: "ВНИМАНИЕ", INFO: "ИНФО"}
LEVEL_ORDER = {ERROR: 0, WARN: 1, INFO: 2}


class Flag(NamedTuple):
    """Флаг качества: уровень (ERROR/WARN/INFO) и текст для пользователя."""

    level: str
    text: str

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES.get(self.level, self.level)


@dataclass(eq=False)   # образцы сравниваются как объекты: два повтора с одним именем — разные образцы
class Sample:
    """Кривая распределения частиц по размерам.

    size_um — верхние границы интервалов, мкм (по возрастанию);
    cum_pct — накопленная объёмная доля частиц мельче size_um, % (ΣQ).
    Если исходная сетка начинается не с 0, в начало добавлена точка (0, 0).
    """

    name: str
    size_um: np.ndarray
    cum_pct: np.ndarray
    meas_id: str = ""
    file: str = ""
    sheet: str = ""
    meta: dict = field(default_factory=dict)
    flags: list[Flag] = field(default_factory=list)
    source: str = "table"  # "fritsch" | "table"
    members: list[str] = field(default_factory=list)  # id измерений, если это среднее повторов

    def __post_init__(self):
        self.size_um = np.asarray(self.size_um, dtype=float)
        self.cum_pct = np.asarray(self.cum_pct, dtype=float)
        if self.size_um.shape != self.cum_pct.shape:
            raise ValueError("size_um и cum_pct разной длины")
        if len(self.size_um) and self.size_um[0] > 0:
            self.size_um = np.concatenate([[0.0], self.size_um])
            self.cum_pct = np.concatenate([[0.0], self.cum_pct])
        if isinstance(self.file, Path):
            self.file = str(self.file)

    @property
    def label(self) -> str:
        """Подпись для отчётов: имя + номер измерения."""
        return f"{self.name} ({self.meas_id})" if self.meas_id else self.name

    def add_flag(self, level: str, text: str) -> None:
        if (level, text) not in self.flags:
            self.flags.append(Flag(level, text))

    @property
    def worst_level(self) -> str | None:
        """Самый серьёзный уровень флага (для иконки) или None."""
        if not self.flags:
            return None
        return min((f[0] for f in self.flags), key=lambda lv: LEVEL_ORDER.get(lv, 9))


# Одно измерение прибора и образец (в т.ч. среднее повторов) описываются одним классом.
Measurement = Sample
