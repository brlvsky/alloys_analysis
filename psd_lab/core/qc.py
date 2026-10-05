"""М8. Чек-лист качества измерения (хранится в measurements.qc_checklist, JSON)."""
from __future__ import annotations

OBSCURATION_WINDOW = (0.0, 40.0)   # как флаги качества: < 0 — ОШИБКА, > 40 — ВНИМАНИЕ (ТЗ)

# (ключ, текст, автоматический)
ITEMS = [
    ("background", "Фон проверен (стабилен, обскурация после пробы > 0)", False),
    ("obscuration", "Обскурация в допустимом окне (0…40 %) — автоматически по данным прибора", True),
    ("subsamples", "Повторы сделаны из независимых подпроб", False),
    ("ultrasound", "Проведён тест ультразвуком (агломераты / настоящие частицы)", False),
    ("model", "Модель расчёта указана (Фраунгофер или Ми + оптические константы)", False),
]
KEYS = [k for k, _, _ in ITEMS]


def auto_obscuration(meta: dict) -> bool:
    obs = meta.get("obscuration")
    return obs is not None and OBSCURATION_WINDOW[0] < obs <= OBSCURATION_WINDOW[1]


def checklist(saved: dict | None, meta: dict) -> dict[str, bool]:
    """Сохранённые ручные отметки + автоматический пункт про обскурацию."""
    saved = saved or {}
    out = {k: bool(saved.get(k, False)) for k in KEYS}
    out["obscuration"] = auto_obscuration(meta)
    return out


def combine(lists: list[dict]) -> dict[str, bool]:
    """Для среднего повторов пункт выполнен, только если выполнен у всех измерений."""
    if not lists:
        return {k: False for k in KEYS}
    return {k: all(cl.get(k, False) for cl in lists) for k in KEYS}


def label(cl: dict) -> str:
    return f"{sum(bool(cl.get(k)) for k in KEYS)}/{len(KEYS)}"
