"""Отчёты: summary.xlsx (Сводка / Кривые / Флаги) и самодостаточный report.html.

Плюс пакетный режим: обработать папку целиком без GUI.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import io
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import APP_NAME, PROJECT, __version__
from . import expand_paths, load
from .metrics import average_repeats, compute, window_label
from .model import LEVEL_NAMES, LEVEL_ORDER, Sample
from .plots import common_axes, draw_compare, draw_sample, new_figure, plot_all

SOURCE_NAMES = {"fritsch": "Fritsch", "table": "таблица"}


# ---------------------------------------------------------------- данные сводки
def summary_columns(windows) -> list[str]:
    cols = ["Образец", "Измерения", "Файл", "d10, мкм", "d50, мкм", "d90, мкм", "span",
            "D[4,3], мкм", "D[3,2], мкм"]
    cols += [f"{window_label(lo, hi)} мкм, %" for lo, hi in windows]
    cols += ["Обскурация, %", "Error", "Флаги", "Источник"]
    return cols


def flags_short(s: Sample) -> str:
    """Кратко: 'ОШИБКА 1, ИНФО 1' или пусто."""
    if not s.flags:
        return ""
    counts = {}
    for f in s.flags:
        counts[f[0]] = counts.get(f[0], 0) + 1
    order = sorted(counts, key=lambda lv: LEVEL_ORDER.get(lv, 9))
    return ", ".join(f"{LEVEL_NAMES.get(lv, lv)} {counts[lv]}" for lv in order)


def summary_rows(samples: list[Sample], windows) -> list[list]:
    rows = []
    for s in samples:
        m = compute(s, windows)
        obs = s.meta.get("obscuration")
        err = s.meta.get("error")
        rows.append([
            s.name, ", ".join(s.members) if s.members else s.meas_id, Path(s.file).name if s.file else "",
            m["d10"], m["d50"], m["d90"], m["span"], m["d43"], m["d32"],
            *m["fractions"].values(),
            obs, err, flags_short(s), SOURCE_NAMES.get(s.source, s.source),
        ])
    return rows


def grouped_flags(samples: list[Sample]) -> list[tuple[tuple[str, str], list[str]]]:
    """Одинаковые флаги разных образцов (например, TradeOff файла) — одной строкой."""
    groups: dict[tuple[str, str], list[str]] = {}
    for s in samples:
        for f in s.flags:
            groups.setdefault((f[0], f[1]), []).append(s.label)
    return sorted(groups.items(), key=lambda kv: (LEVEL_ORDER.get(kv[0][0], 9), kv[1][0]))


def interval_q(s: Sample) -> np.ndarray:
    """Q, % в интервале, заканчивающемся в каждой точке сетки (первая точка — 0)."""
    return np.concatenate([[0.0], np.diff(s.cum_pct)])


# ---------------------------------------------------------------- Excel
def write_xlsx(samples: list[Sample], path: Path, windows) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    head_font = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="D9D9D9")
    wb = Workbook()

    ws = wb.active
    ws.title = "Сводка"
    cols = summary_columns(windows)
    ws.append(cols)
    for r in summary_rows(samples, windows):
        ws.append([_xl(v) for v in r])
    for c in range(1, len(cols) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font, cell.fill = head_font, head_fill
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(c)].width = 22 if c in (1, 2, 3) else 11
    ws.column_dimensions[get_column_letter(cols.index("Флаги") + 1)].width = 24
    ws.column_dimensions[get_column_letter(cols.index("Источник") + 1)].width = 24
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=len(cols) - 2):
        for cell in row:
            if isinstance(cell.value, float):
                cell.number_format = "0.00"
    ws.freeze_panes = "B2"

    wc = wb.create_sheet("Кривые")
    for i, s in enumerate(samples):
        c0 = i * 4 + 1
        wc.cell(row=1, column=c0, value=s.label).font = head_font
        for j, h in enumerate(("Размер, мкм", "ΣQ, %", "Q, %")):
            cell = wc.cell(row=2, column=c0 + j, value=h)
            cell.font, cell.fill = head_font, head_fill
        q = interval_q(s)
        for k, (x, c, qq) in enumerate(zip(s.size_um, s.cum_pct, q)):
            wc.cell(row=3 + k, column=c0, value=float(x))
            wc.cell(row=3 + k, column=c0 + 1, value=round(float(c), 4))
            wc.cell(row=3 + k, column=c0 + 2, value=round(float(qq), 4))
    wc.freeze_panes = "A3"

    wf = wb.create_sheet("Флаги")
    wf.append(["Образец", "Измерения", "Уровень", "Описание"])
    for c in range(1, 5):
        wf.cell(row=1, column=c).font, wf.cell(row=1, column=c).fill = head_font, head_fill
    for s in samples:
        for f in sorted(s.flags, key=lambda f: LEVEL_ORDER.get(f[0], 9)):
            wf.append([s.name, ", ".join(s.members) or s.meas_id, LEVEL_NAMES.get(f[0], f[0]), f[1]])
    for col, w in zip("ABCD", (22, 20, 12, 100)):
        wf.column_dimensions[col].width = w

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def _xl(v):
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else float(v)
    return v


# ---------------------------------------------------------------- HTML
def _fig_b64(fig, dpi=110) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _fmt(v, nd=2) -> str:
    if v is None:
        return "—"
    if isinstance(v, (float, np.floating)):
        return "—" if not np.isfinite(v) else f"{v:.{nd}f}".replace(".", ",")
    return html.escape(str(v))


LEVEL_CSS = {"ERROR": "err", "WARN": "warn", "INFO": "info"}

CSS = """
body{font-family:Tahoma,Verdana,Arial,sans-serif;font-size:14px;color:#000;background:#fff;
     max-width:1100px;margin:0 auto;padding:16px;line-height:1.45}
h1{font-size:22px;background:#000080;color:#fff;padding:6px 10px;margin:0 0 4px}
h2{font-size:17px;border-bottom:2px solid #000080;padding-bottom:2px;margin-top:28px}
h3{font-size:15px;margin:18px 0 4px}
.meta{color:#444;font-size:13px}
table{border-collapse:collapse;font-size:12.5px;margin:6px 0}
th,td{border:1px solid #808080;padding:3px 6px;vertical-align:top}
th{background:#c0c0c0;text-align:center}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.scroll{overflow-x:auto}
.badge{display:inline-block;min-width:76px;text-align:center;font-weight:bold;padding:0 4px;
       border:1px solid #000;margin-right:6px}
.err{background:#ff0000;color:#fff}.warn{background:#ffff00;color:#000}.info{background:#0000ff;color:#fff}
img{max-width:100%;border:1px solid #808080}
.card{margin:14px 0 24px}
.note{background:#ffffe1;border:1px solid #000;padding:6px 10px;font-size:13px}
ul.flags{list-style:none;padding-left:0}
ul.flags li{margin:3px 0}
"""


def write_html(samples: list[Sample], path: Path, *, windows, lang="en", bin_um=None, xmax=None,
               independent_axes=False, show_name=True, log_x=True, files=None, skipped=None) -> Path:
    files = files or sorted({s.file for s in samples})
    now = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    cols = summary_columns(windows)
    rows = summary_rows(samples, windows)
    num_cols = set(range(3, len(cols) - 2))
    decimals = {i: 2 for i in num_cols}
    decimals.update({i: 1 for i in range(9, 9 + len(windows))})
    decimals[len(cols) - 4] = 0  # обскурация
    decimals[len(cols) - 3] = 3  # Error

    h = [f"<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
         f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Отчёт по гранулометрии</title><style>{CSS}</style></head><body>"]
    h.append("<h1>Гранулометрический состав порошков</h1>")
    h.append(f"<p class='meta'>Проект: «{html.escape(PROJECT)}». Сформировано {now} программой "
             f"{APP_NAME} {__version__}. Образцов: {len(samples)}.</p>")
    h.append("<p class='meta'>Файлы: " + ", ".join(html.escape(Path(f).name) for f in files) + "</p>")

    # Сводка
    h.append("<h2>1. Сводная таблица</h2><div class='scroll'><table><tr>")
    h += [f"<th>{html.escape(c)}</th>" for c in cols]
    h.append("</tr>")
    for r in rows:
        h.append("<tr>" + "".join(
            f"<td class='n'>{_fmt(v, decimals[i])}</td>" if i in num_cols
            else f"<td>{_fmt(v)}</td>" for i, v in enumerate(r)) + "</tr>")
    h.append("</table></div>")
    h.append("<p class='note'><b>Обозначения.</b> ΣQ — накопленная объёмная доля частиц мельче данного "
             "размера, %; Q — доля объёма в интервале, %. d10, d50, d90 — размеры, мельче которых 10, 50 и "
             "90 % объёма порошка; span = (d90 − d10)/d50 — ширина распределения. D[4,3] — средний по объёму "
             "диаметр, D[3,2] — средний по поверхности (Заутера). Доли по окнам — объёмный процент частиц в "
             "диапазоне размеров. Кривые не обрезаются и не перенормируются: если кривая не доходит до 100 %, "
             "это показано флагом. Повторные измерения с одинаковым названием усреднены.</p>")

    # Флаги
    h.append("<h2>2. Качество измерений</h2>")
    flagged = [s for s in samples if s.flags]
    if not flagged:
        h.append("<p>Замечаний нет.</p>")
    else:
        h.append("<ul class='flags'>")
        for (lv, text), labels in grouped_flags(samples):
            css = LEVEL_CSS.get(lv, "info")
            h.append(f"<li><span class='badge {css}'>{LEVEL_NAMES.get(lv, lv)}</span>"
                     f"<b>{html.escape(', '.join(labels))}</b>: {html.escape(text)}</li>")
        h.append("</ul>")
        h.append("<p class='note'>ОШИБКА — результату доверять нельзя, измерение нужно повторить. "
                 "ВНИМАНИЕ — результат возможен, но с оговоркой. ИНФО — к сведению при сравнении образцов. "
                 "Поле Error прибора показано в таблице без оценки (единицы в экспорте не указаны).</p>")

    # Сравнение
    groups = _groups(samples)
    fig = new_figure()
    draw_compare(fig, groups, lang=lang, log_x=log_x, xmax=xmax)
    h.append("<h2>3. Сравнение накопленных кривых</h2>")
    h.append(f"<img alt='Сравнение' src='data:image/png;base64,{_fig_b64(fig)}'>")

    # По образцам
    h.append("<h2>4. Распределения по образцам</h2>")
    for grp in groups:
        shared = (None, None) if independent_axes else common_axes(grp, bin_um, xmax)
        h.append(f"<h3>Файл {html.escape(Path(grp[0].file).name)}</h3>")
        for s in grp:
            draw_sample(fig, s, lang=lang, bin_um=bin_um, xmax=xmax or shared[0], ymax=shared[1],
                        show_name=show_name)
            m = compute(s, windows)
            h.append("<div class='card'>")
            h.append(f"<b>{html.escape(s.label)}</b> — d10 {_fmt(m['d10'])}, d50 {_fmt(m['d50'])}, "
                     f"d90 {_fmt(m['d90'])} мкм; D[4,3] {_fmt(m['d43'])} мкм")
            if s.meta.get("obscuration") is not None:
                h.append(f"; обскурация {_fmt(s.meta['obscuration'], 0)} %")
            h.append(f"<br><img alt='{html.escape(s.label)}' src='data:image/png;base64,{_fig_b64(fig)}'>")
            h.append("</div>")

    if skipped:
        h.append("<h2>Пропущенные файлы</h2><ul>")
        h += [f"<li>{html.escape(Path(f).name)}: {html.escape(why)}</li>" for f, why in skipped]
        h.append("</ul>")
    h.append("</body></html>")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(h), encoding="utf-8")
    return path


def _groups(samples: list[Sample]) -> list[list[Sample]]:
    groups: dict[str, list[Sample]] = {}
    for s in samples:
        groups.setdefault(s.file, []).append(s)
    return list(groups.values())


# ---------------------------------------------------------------- пакетный режим
@dataclass
class BatchResult:
    samples: list = field(default_factory=list)
    files: list = field(default_factory=list)
    skipped: list = field(default_factory=list)   # [(файл, причина)]
    outputs: list = field(default_factory=list)


def load_many(paths, average=True, log=print) -> BatchResult:
    res = BatchResult()
    for f in expand_paths(paths):
        try:
            ss = load(f)
        except Exception as e:  # noqa: BLE001 — файл пользователя может быть любым
            res.skipped.append((f, f"не удалось прочитать: {e}"))
            log(f"ПРОПУЩЕН  {f.name}: не удалось прочитать ({e})")
            continue
        if not ss:
            res.skipped.append((f, "не найдено распределений"))
            log(f"ПРОПУЩЕН  {f.name}: не найдено распределений")
            continue
        src = "экспорт Fritsch" if ss[0].source == "fritsch" else "таблица"
        log(f"ЗАГРУЖЕН  {f.name}: {len(ss)} изм. ({src})")
        res.files.append(f)
        res.samples.extend(average_repeats(ss) if average else ss)
    return res


def run_batch(src, out, settings=None, log=print) -> BatchResult:
    from .settings import Settings

    st = settings or Settings()
    out = Path(out)
    res = load_many([src] if isinstance(src, (str, Path)) else src, average=st.average, log=log)
    if not res.samples:
        log("Нет данных для обработки.")
        return res
    groups = [(g[0].file, g) for g in _groups(res.samples)]
    made = plot_all(groups, out, lang=st.lang, bin_um=st.bin_um, xmax=st.xmax,
                    independent_axes=st.independent_axes, show_name=st.show_name, log_x=st.compare_log)
    res.outputs += [p for _, p in made]
    log(f"Графики: {len(made)} PNG в {out}")
    res.outputs.append(write_xlsx(res.samples, out / "summary.xlsx", st.windows_tuples))
    res.outputs.append(write_html(res.samples, out / "report.html", windows=st.windows_tuples, lang=st.lang,
                                  bin_um=st.bin_um, xmax=st.xmax, independent_axes=st.independent_axes,
                                  show_name=st.show_name, log_x=st.compare_log, files=res.files,
                                  skipped=res.skipped))
    log(f"Отчёт: {out / 'report.html'}; таблица: {out / 'summary.xlsx'}")
    return res
