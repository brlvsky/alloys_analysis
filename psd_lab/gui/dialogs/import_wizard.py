"""Файл → Импорт таблицы вручную: мастер, где пользователь сам показывает, где размеры и где проценты.

Нужен, когда автоматическое распознавание не справилось или поняло таблицу не так. Настройка
(«рецепт») запоминается по отпечатку файла (SHA-1) — при следующем открытии файл читается так же.
"""
from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ...core.io_smart import KINDS, UNITS, column_letter, find_axes, normalize, parse_recipe, transpose
from ...core.io_table import read_grids
from ...core.metrics import d_at
from .. import theme
from ..widgets import Dialog, NoteBox, groupbox

PREVIEW_ROWS = 400
PREVIEW_COLS = 60


def _cell_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",") if math.isfinite(v) else ""
    if hasattr(v, "strftime"):
        return v.strftime("%d.%m.%Y")
    return str(v)


class ImportWizard(Dialog):
    """result — (образцы, рецепт) после «Загрузить», иначе None."""

    def __init__(self, parent, path: Path, recipe: dict | None = None):
        super().__init__(parent, f"Мастер импорта — {Path(path).name}", buttons=("OK", "Отмена"))
        self.resizable(True, True)
        self.buttons["OK"].configure(text="Загрузить")
        self.path = Path(path)
        self.grids = read_grids(self.path)
        if not self.grids:
            raise ValueError("в файле нет листов с данными")
        b = self.body
        NoteBox(b, "выберите лист и покажите, в каком столбце размеры частиц, в каких строках данные и в каких "
                   "столбцах проценты. Если таблица «боком» (размеры в строке), отметьте «по строкам». "
                   "Ниже сразу видно, что получится. Настройка запомнится для этого файла.",
                title="Как пользоваться:").pack(fill="x", pady=(0, theme.px(6)))

        top = tk.Frame(b, background=theme.FACE)
        top.pack(fill="x")
        tk.Label(top, text="Лист:").pack(side="left")
        self.cb_sheet = ttk.Combobox(top, state="readonly", width=24, values=[n for n, _ in self.grids],
                                     font=theme.FONTS["ui"])
        self.cb_sheet.pack(side="left", padx=(theme.px(4), theme.px(16)))
        tk.Label(top, text="Таблица:").pack(side="left")
        self.v_orient = tk.StringVar(value="cols")
        for val, txt in (("cols", "по столбцам (обычно)"), ("rows", "по строкам (размеры в строке)")):
            tk.Radiobutton(top, text=txt, value=val, variable=self.v_orient, command=self._on_sheet,
                           background=theme.FACE, activebackground=theme.FACE).pack(side="left", padx=theme.px(4))

        # предпросмотр листа
        g = groupbox(b, "Содержимое листа (первые строки)")
        g.pack(fill="both", expand=True, pady=(theme.px(6), 0))
        frame = tk.Frame(g, relief="sunken", borderwidth=2, background=theme.FACE)
        frame.pack(fill="both", expand=True)
        self.grid_view = ttk.Treeview(frame, show="headings", height=12, selectmode="none")
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.grid_view.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=self.grid_view.xview)
        self.grid_view.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.grid_view.pack(fill="both", expand=True)
        self.grid_view.tag_configure("axis", background="#FFFFE1")

        # настройки
        cols = tk.Frame(b, background=theme.FACE)
        cols.pack(fill="x", pady=(theme.px(6), 0))
        g1 = groupbox(cols, "Размеры частиц")
        g1.pack(side="left", fill="y", padx=(0, theme.px(6)))
        tk.Label(g1, text="Столбец:").grid(row=0, column=0, sticky="w")
        self.cb_axis = ttk.Combobox(g1, state="readonly", width=24, font=theme.FONTS["ui"])
        self.cb_axis.grid(row=0, column=1, columnspan=3, sticky="w", pady=theme.px(2))
        tk.Label(g1, text="Строки: с").grid(row=1, column=0, sticky="w")
        self.sp_r0 = tk.Spinbox(g1, from_=1, to=100000, width=6, command=self.update_preview)
        self.sp_r0.grid(row=1, column=1, sticky="w", pady=theme.px(2))
        tk.Label(g1, text="по").grid(row=1, column=2, padx=theme.px(4))
        self.sp_r1 = tk.Spinbox(g1, from_=1, to=100000, width=6, command=self.update_preview)
        self.sp_r1.grid(row=1, column=3, sticky="w")
        tk.Label(g1, text="Единицы:").grid(row=2, column=0, sticky="w")
        self.cb_unit = ttk.Combobox(g1, state="readonly", width=18, font=theme.FONTS["ui"],
                                    values=[v[0] for v in UNITS.values()])
        self.cb_unit.grid(row=2, column=1, columnspan=3, sticky="w", pady=theme.px(2))

        g2 = groupbox(cols, "Распределение")
        g2.pack(side="left", fill="both", expand=True)
        tk.Label(g2, text="Столбцы с данными (можно несколько — Ctrl+щелчок):").grid(row=0, column=0, sticky="w")
        lf = tk.Frame(g2, relief="sunken", borderwidth=2)
        lf.grid(row=1, column=0, sticky="nsew")
        self.lb_data = tk.Listbox(lf, selectmode="extended", height=4, exportselection=False, relief="flat",
                                  borderwidth=0, width=36)
        self.lb_data.pack(fill="both", expand=True)
        tk.Label(g2, text="Вид данных:").grid(row=2, column=0, sticky="w", pady=(theme.px(4), 0))
        self.cb_kind = ttk.Combobox(g2, state="readonly", width=60, values=list(KINDS.values()),
                                    font=theme.FONTS["ui"])
        self.cb_kind.grid(row=3, column=0, sticky="w")
        g2.columnconfigure(0, weight=1)

        # итог
        g3 = groupbox(b, "Что получится")
        g3.pack(fill="x", pady=(theme.px(6), 0))
        self.result_label = tk.Label(g3, text="", justify="left", anchor="w", wraplength=theme.px(820))
        self.result_label.pack(fill="x")

        for w in (self.cb_axis, self.cb_unit, self.cb_kind):
            w.bind("<<ComboboxSelected>>", lambda e: self.update_preview())
        self.cb_sheet.bind("<<ComboboxSelected>>", lambda e: self._on_sheet())
        self.lb_data.bind("<<ListboxSelect>>", lambda e: self.update_preview())
        for sp in (self.sp_r0, self.sp_r1):
            sp.bind("<KeyRelease>", lambda e: self.update_preview())
        self.cb_axis.bind("<<ComboboxSelected>>", lambda e: self._on_axis(), add="+")

        self.samples = None
        self.recipe = None
        self._apply_recipe(recipe)

    # ---------------------------------------------------------------- данные листа
    def _rows(self):
        name = self.cb_sheet.get()
        rows = next(r for n, r in self.grids if n == name)
        return transpose(rows) if self.v_orient.get() == "rows" else rows

    def _header(self, rows, c, r0=None) -> str:
        """Подпись столбца — первый текст сверху (до строки r0)."""
        stop = len(rows) if r0 is None else r0
        for r in range(min(stop, 30)):
            v = rows[r][c] if c < len(rows[r]) else None
            if isinstance(v, str) and v.strip():
                return v.strip()[:30]
        return ""

    def _fill_grid(self, rows):
        tv = self.grid_view
        tv.delete(*tv.get_children())
        ncols = min(PREVIEW_COLS, max((len(r) for r in rows), default=0))
        ids = ["#"] + [column_letter(c) for c in range(ncols)]
        tv.configure(columns=ids)
        ch = theme.px(7)
        tv.heading("#", text="№")
        tv.column("#", width=theme.px(40), anchor="e", stretch=False)
        for c in range(ncols):
            tv.heading(ids[c + 1], text=column_letter(c))
            tv.column(ids[c + 1], width=12 * ch, anchor="w", stretch=False)
        self._ncols = ncols
        for r, row in enumerate(rows[:PREVIEW_ROWS]):
            vals = [r + 1] + [_cell_text(row[c]) if c < len(row) else "" for c in range(ncols)]
            tv.insert("", "end", iid=str(r), values=vals)
        names = [f"{column_letter(c)} — {self._header(rows, c)}" if self._header(rows, c) else column_letter(c)
                 for c in range(ncols)]
        self.cb_axis.configure(values=names)
        self.lb_data.delete(0, "end")
        for n in names:
            self.lb_data.insert("end", n)

    def _on_sheet(self):
        rows = self._rows()
        self._fill_grid(rows)
        self._autodetect(rows)
        self.update_preview()

    def _on_axis(self):
        """При выборе столбца размеров — подобрать строки (самый длинный ряд чисел в нём)."""
        rows = normalize(self._rows())
        c = self.cb_axis.current()
        best = (0, 0)
        start = None
        for r, row in enumerate(rows):
            v = row[c] if c < len(row) else None
            ok = isinstance(v, float) and math.isfinite(v)
            if ok and start is None:
                start = r
            if (not ok or r == len(rows) - 1) and start is not None:
                end = r if ok else r - 1
                if end - start + 1 > best[1]:
                    best = (start, end - start + 1)
                start = None
        if best[1]:
            self._set_rows(best[0], best[0] + best[1] - 1)
        self.update_preview()

    def _set_rows(self, r0, r1):
        for sp, v in ((self.sp_r0, r0 + 1), (self.sp_r1, r1 + 1)):
            sp.delete(0, "end")
            sp.insert(0, str(v))

    def _autodetect(self, rows):
        """Начальное предложение — то, что нашло бы автоматическое распознавание; иначе первая ось
        и числовые столбцы справа от неё."""
        from ...core.io_smart import parse_sheet

        found = []
        try:
            raw = next(r for n, r in self.grids if n == self.cb_sheet.get())
            found = parse_sheet(raw, self.cb_sheet.get(), self.path)
        except Exception:  # noqa: BLE001
            found = []
        orient = "rows" if self.v_orient.get() == "rows" else "cols"
        found = [s for s in found if s.meta.get("src_orient") == orient and "src_col" in s.meta]
        self.cb_unit.current(0)
        self.cb_kind.current(0)
        self.lb_data.selection_clear(0, "end")
        if found:
            axis = found[0].meta["src_axis"]
            r0, r1 = found[0].meta["src_rows"]
            if axis < self._ncols:
                self.cb_axis.current(axis)
                self._set_rows(r0, r1)
                for s in found:
                    if s.meta["src_axis"] == axis and s.meta["src_col"] < self._ncols:
                        self.lb_data.selection_set(s.meta["src_col"])
                return
        norm = normalize(rows)
        axes = [a for a in find_axes(norm) if a.kind == "num"]
        if axes:
            ax = max(axes, key=lambda a: (a.n, -a.col))
            self.cb_axis.current(min(ax.col, self._ncols - 1))
            self._set_rows(ax.r0 + (1 if ax.lead is not None else 0),
                           ax.r0 + ax.n - 1 - (1 if ax.tail is not None else 0))
            for c in range(ax.col + 1, self._ncols):
                vals = [norm[r][c] if c < len(norm[r]) else None for r in range(ax.r0, ax.r0 + ax.n)]
                if sum(isinstance(v, float) for v in vals) >= 0.8 * len(vals):
                    self.lb_data.selection_set(c)
        elif self._ncols:
            self.cb_axis.current(0)
            self._on_axis()

    def _apply_recipe(self, recipe):
        self.cb_sheet.set(recipe.get("sheet") if recipe and recipe.get("sheet") in
                          [n for n, _ in self.grids] else self.grids[0][0])
        self.v_orient.set((recipe or {}).get("orient", "cols"))
        rows = self._rows()
        self._fill_grid(rows)
        if not recipe:
            self._autodetect(rows)
        else:
            self.cb_axis.current(min(int(recipe["axis"]), self._ncols - 1))
            self._set_rows(int(recipe["r0"]), int(recipe["r1"]))
            self.lb_data.selection_clear(0, "end")
            for c in recipe.get("data", []):
                if int(c) < self._ncols:
                    self.lb_data.selection_set(int(c))
            self.cb_unit.current(list(UNITS).index(recipe.get("unit", "um")))
            self.cb_kind.current(list(KINDS).index(recipe.get("kind", "auto")))
        self.update_preview()

    # ---------------------------------------------------------------- рецепт и предпросмотр
    def build_recipe(self) -> dict:
        try:
            r0, r1 = int(self.sp_r0.get()) - 1, int(self.sp_r1.get()) - 1
        except ValueError as e:
            raise ValueError("номера строк — целые числа") from e
        if r1 - r0 < 1:
            raise ValueError("выберите хотя бы 2 строки с размерами")
        data = list(self.lb_data.curselection())
        axis = self.cb_axis.current()
        if axis < 0:
            raise ValueError("выберите столбец с размерами")
        if not data:
            raise ValueError("выберите хотя бы один столбец с данными")
        if axis in data:
            raise ValueError("столбец размеров не может быть одновременно столбцом данных")
        return {"sheet": self.cb_sheet.get(), "orient": self.v_orient.get(), "axis": axis, "r0": r0, "r1": r1,
                "data": data, "kind": list(KINDS)[max(0, self.cb_kind.current())],
                "unit": list(UNITS)[max(0, self.cb_unit.current())]}

    def update_preview(self):
        for iid in self.grid_view.tag_has("axis"):
            self.grid_view.item(iid, tags=())
        try:
            recipe = self.build_recipe()
            for r in range(recipe["r0"], min(recipe["r1"] + 1, PREVIEW_ROWS)):
                if self.grid_view.exists(str(r)):
                    self.grid_view.item(str(r), tags=("axis",))
            samples = parse_recipe(self._rows() if recipe["orient"] == "cols" else
                                   next(r for n, r in self.grids if n == recipe["sheet"]),
                                   recipe, recipe["sheet"], self.path)
        except Exception as e:  # noqa: BLE001 — показываем пользователю, что не так
            self.result_label.configure(text=f"Пока не получается: {e}", foreground="#FF0000")
            self.samples = None
            return
        lines = []
        for s in samples:
            d50 = d_at(s, 50)
            d50s = "—" if d50 != d50 else f"{d50:.2f}".replace(".", ",")
            lines.append(f"• {s.name}: {len(s.size_um) - 1} точек, {s.size_um[1]:g}–{s.size_um[-1]:g} мкм, "
                         f"ΣQ в конце {s.cum_pct[-1]:.1f} %, d50 = {d50s} мкм".replace(".", ","))
        notes = list(dict.fromkeys(n for s in samples for n in s.meta.get("import_notes", [])))
        txt = "\n".join(lines) + ("\nКак прочитано: " + "; ".join(notes) if notes else "")
        self.result_label.configure(text=txt, foreground=theme.TEXT)
        self.samples, self.recipe = samples, recipe

    def on_ok(self):
        self.update_preview()
        if not self.samples:
            messagebox.showwarning("Мастер импорта", self.result_label.cget("text"), parent=self)
            return
        self.result = (self.samples, self.recipe)
        self.destroy()
