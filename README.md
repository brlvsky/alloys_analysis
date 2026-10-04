# PSD toolkit

Инструмент для обработки гранулометрии порошков (лазерная дифракция): графики, сводная таблица, отчёт, база «структура — свойства».

*Заготовка. Полная инструкция появится после этапа 3.*

## Быстрый старт (для разработки)

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip ...
.venv/bin/python -m psd_toolkit --help
.venv/bin/pytest
```

Исходные файлы кладите в `data/raw/` (их программа никогда не изменяет).
