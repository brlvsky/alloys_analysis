"""Вкладка «Сводка»: таблица метрик, сортировка по заголовку, Ctrl+C — копирование табами для Excel."""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from ...core.report import summary_columns, summary_rows
from .. import theme
from ..widgets import PanelTitle, sunken

# ширина колонок в «символах» шрифта (примерно)
WIDE = {"Образец": 16, "Измерения": 14, "Файл": 12, "Флаги": 16, "Источник": 9, "QC": 5}


def short(name: str) -> str:
    """'d10, мкм' → 'd10'; '<15 мкм, %' → '<15'; 'Обскурация, %' → 'Обскур., %'."""
    if name.startswith("Обскурация"):
        return "Обскур., %"
    return name.split(", ")[0].replace(" мкм", "")


def _fmt(v, decimals):
    if v is None:
        return ""
    if isinstance(v, float):
        return "" if not math.isfinite(v) else f"{v:.{decimals}f}".replace(".", ",")
    return str(v)


def _excel(v) -> str:
    """Значение для вставки в русский Excel: десятичная запятая."""
    if isinstance(v, float):
        return "" if not math.isfinite(v) else f"{v:.6g}".replace(".", ",")
    return "" if v is None else str(v)


class SummaryTab(tk.Frame):
    def __init__(self, parent, on_select=None, icon=None):
        super().__init__(parent, background=theme.FACE)
        PanelTitle(self, "Сводная таблица: размеры — мкм, доли — % объёма. Ctrl+C — копировать для Excel").pack(fill="x")
        frame = sunken(self)
        frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.icon = icon
        self.tree = ttk.Treeview(frame, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="QC")
        self.tree.column("#0", width=theme.icon_px() + theme.px(58), minwidth=theme.icon_px() + theme.px(12),
                         stretch=False, anchor="center")
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Control-c>", self.copy)
        self.tree.bind("<Control-C>", self.copy)
        self.tree.bind("<Control-a>", lambda e: self.tree.selection_set(self.tree.get_children()))
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda e: on_select(self.selected_samples()))
        self.cols: list[str] = []
        self.rows: dict[str, list] = {}
        self.samples: dict[str, object] = {}
        self.decimals: dict[int, int] = {}
        self._sort = (None, False)

    def show(self, samples, windows, qc=None):
        self.cols = summary_columns(windows, with_qc=qc is not None)
        nfr = len(windows)
        self.decimals = {i: 2 for i in range(3, 9)}
        self.decimals.update({i: 1 for i in range(9, 9 + nfr)})
        self.decimals.update({9 + nfr: 0, 10 + nfr: 3})
        self.tree.delete(*self.tree.get_children())
        ids = [f"c{i}" for i in range(len(self.cols))]
        self.tree.configure(columns=ids)
        import tkinter.font as tkfont

        char = tkfont.Font(root=self, font=theme.FONTS["ui"]).measure("0") + 1
        for cid, name in zip(ids, self.cols):
            w = WIDE.get(name, 8) * char
            self.tree.heading(cid, text=short(name), command=lambda c=cid: self.sort_by(c))
            self.tree.column(cid, width=w, minwidth=40, stretch=False,
                             anchor="w" if name in WIDE else "e")
        self.rows, self.samples = {}, {}
        for s, r in zip(samples, summary_rows(samples, windows, qc)):
            img = self.icon(s.worst_level) if self.icon else ""
            iid = self.tree.insert("", "end", image=img, text=f" {qc.get(s.label, '')}" if qc else "",
                                   values=[_fmt(v, self.decimals.get(i, 2)) for i, v in enumerate(r)])
            self.rows[iid], self.samples[iid] = r, s
        if self._sort[0] is not None:
            self.sort_by(self._sort[0], keep=True)

    def sort_by(self, cid, keep=False):
        idx = int(cid[1:])
        desc = self._sort[1] if keep else (self._sort[0] == cid and not self._sort[1])
        self._sort = (cid, desc)

        def key(iid):
            v = self.rows[iid][idx]
            if isinstance(v, (int, float)) and math.isfinite(v):
                return (0, v, "")
            return (1, 0, str(v or "").lower())

        items = sorted(self.tree.get_children(), key=key, reverse=desc)
        for pos, iid in enumerate(items):
            self.tree.move(iid, "", pos)
        for i, name in enumerate(self.cols):
            arrow = (" ▼" if desc else " ▲") if f"c{i}" == cid else ""
            self.tree.heading(f"c{i}", text=short(name) + arrow)

    def selected_samples(self):
        return [self.samples[i] for i in self.tree.selection() if i in self.samples]

    def copy(self, _e=None):
        sel = self.tree.selection() or self.tree.get_children()
        lines = ["\t".join(self.cols)]
        for iid in sel:
            r = self.rows[iid]
            # десятичная запятая — чтобы русский Excel понял числа
            lines.append("\t".join(_excel(v) for v in r))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        return "break"
