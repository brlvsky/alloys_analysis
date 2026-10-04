# PSD-Lab

Программа для анализа гранулометрии порошков (лазерный анализатор Fritsch ANALYSETTE 22 и обычные таблицы):
графики распределения, сводная таблица, отчёт для руководителя.

*Заготовка — полная инструкция появится в конце работы (этап 8).*

## Запуск из исходников

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m psd_lab                              (окно программы)
.venv\Scripts\python -m psd_lab --batch data\raw --out out   (без окна: графики + summary.xlsx + report.html)
```

Исходные файлы кладите в `data\raw\` — программа их никогда не изменяет.
