"""Вкладка «База данных» (М1): партии слева, таблицы справа, формы «Добавить / Изменить / Удалить»."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ...core import db
from .. import theme
from ..dialogs.record import RecordDialog
from ..widgets import NoteBox, PanelTitle, Table, groupbox, sunken


def c(v, nd=2):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.{nd}f}".replace(".", ",")
    return str(v)


# колонки сеток: (поле, заголовок, ширина, знаков после запятой)
GRID = {
    "sem": [("image_path", "Файл снимка", 40, 0), ("magnification", "Увеличение", 10, 0), ("notes", "Примечания", 30, 0)],
    "xrd": [("file_path", "Файл", 40, 0), ("phases", "Фазы", 24, 0), ("notes", "Примечания", 30, 0)],
    "chem": [("O_ppm", "O, ppm", 10, 0), ("N_ppm", "N, ppm", 10, 0), ("H_ppm", "H, ppm", 10, 0), ("other", "Другое", 30, 0)],
    "print_jobs": [("id", "№", 5, 0), ("process", "Процесс", 8, 0), ("machine", "Установка", 16, 0),
                   ("power_W", "P, Вт", 8, 0), ("speed_mm_s", "v, мм/с", 9, 0), ("hatch_um", "h, мкм", 8, 0),
                   ("layer_um", "t, мкм", 8, 0), ("energy_density_J_mm3", "E, Дж/мм³", 10, 1),
                   ("preheat_C", "Подогрев, °C", 11, 0), ("rel_density_pct", "Плотн., %", 9, 1), ("strategy", "Стратегия", 16, 0)],
    "mech_tests": [("job", "Режим печати", 18, 0), ("test_type", "Испытание", 13, 0), ("temp_C", "T, °C", 7, 0),
                   ("uts_MPa", "σв, МПа", 9, 0), ("ys_MPa", "σ0,2, МПа", 10, 0), ("elong_pct", "δ, %", 7, 1),
                   ("cycles", "Циклы", 9, 0), ("notes", "Примечания", 24, 0)],
}


class CrudPanel(tk.Frame):
    """Сетка записей таблицы для выбранной партии + кнопки Добавить / Изменить / Удалить."""

    def __init__(self, parent, tab, table):
        super().__init__(parent, background=theme.FACE)
        self.tab, self.table = tab, table
        bar = tk.Frame(self, background=theme.FACE)
        bar.pack(fill="x", pady=theme.px(4))
        for text, cmd in (("Добавить…", self.add), ("Изменить…", self.edit), ("Удалить", self.remove)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(theme.px(4), 0))
        body = tk.Frame(self, background=theme.FACE)
        body.pack(fill="both", expand=True)
        cols = GRID[table]
        self.grid_ = Table(body, [(h, w, "w" if nd == 0 and k not in ("power_W", "speed_mm_s") else "e")
                                  for k, h, w, nd in cols], height=8)
        self.grid_.pack(side="left", fill="both", expand=True)
        self.grid_.tree.bind("<Double-Button-1>", lambda e: self.edit())
        self.ids: list[int] = []
        self.preview = None
        if table == "sem":
            g = groupbox(body, "Превью")
            g.pack(side="left", fill="y", padx=(theme.px(4), 0))
            self.preview = tk.Label(g, text="Выберите снимок", width=34, height=14, background=theme.FIELD,
                                    relief="sunken", borderwidth=2)
            self.preview.pack(fill="both", expand=True)
            self.grid_.tree.bind("<<TreeviewSelect>>", lambda e: self.show_preview())
            self._img = None

    def refresh(self):
        bid = self.tab.batch_id
        rows = db.rows(self.tab.conn, self.table, bid) if bid else []
        self.ids = [r["id"] for r in rows]
        self.grid_.fill([[c(r[k], nd) if isinstance(r[k], float) else ("" if r[k] is None else r[k])
                          for k, _, _, nd in GRID[self.table]] for r in rows])
        if self.preview is not None:
            self.show_preview()

    def selected_id(self):
        sel = self.grid_.tree.selection()
        if not sel:
            return None
        return self.ids[self.grid_.tree.index(sel[0])]

    def add(self):
        if not self.tab.batch_id:
            messagebox.showinfo("База данных", "Сначала выберите партию слева.", parent=self)
            return
        d = RecordDialog(self, self.tab.conn, self.table, f"{db.TABLE_TITLES[self.table]}: новая запись",
                         batch_id=self.tab.batch_id)
        vals = d.show()
        if vals:
            db.insert(self.tab.conn, self.table, vals, self.tab.batch_id)
            self.tab.changed()

    def edit(self):
        rid = self.selected_id()
        if rid is None:
            return
        row = dict(db.get(self.tab.conn, self.table, rid))
        d = RecordDialog(self, self.tab.conn, self.table, f"{db.TABLE_TITLES[self.table]}: изменить запись",
                         values=row, batch_id=self.tab.batch_id)
        vals = d.show()
        if vals:
            db.update(self.tab.conn, self.table, rid, vals)
            self.tab.changed()

    def remove(self):
        rid = self.selected_id()
        if rid is None:
            return
        extra = " Вместе с режимом печати удалятся его механические испытания." if self.table == "print_jobs" else ""
        if messagebox.askyesno("Удаление", "Удалить выбранную запись?" + extra, parent=self):
            db.delete(self.tab.conn, self.table, rid)
            self.tab.changed()

    def show_preview(self):
        rid = self.selected_id()
        if rid is None:
            self.preview.configure(image="", text="Выберите снимок")
            return
        path = db.get(self.tab.conn, "sem", rid)["image_path"]
        try:
            from PIL import Image, ImageTk

            img = Image.open(path)
            img.thumbnail((theme.px(300), theme.px(240)))
            self._img = ImageTk.PhotoImage(img, master=self)
            self.preview.configure(image=self._img, text="", width=0, height=0)
        except Exception:  # noqa: BLE001 — файл мог быть перемещён или это не картинка
            self.preview.configure(image="", text=f"Не удалось открыть:\n{Path(path or '').name or '—'}")


class DatabaseTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, background=theme.FACE)
        self.app = app
        self.batch_id: int | None = None
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        self._pw, self._sash_set = pw, False

        left = tk.Frame(pw, background=theme.FACE)
        pw.add(left, weight=2)
        PanelTitle(left, "Партии").pack(fill="x")
        self.blist = Table(left, [("Название", 15, "w"), ("Сост.", 5, "w"), ("Добавка", 8, "w"),
                                  ("мас.%", 6, "e"), ("Изм.", 5, "e")], height=14)
        self.blist.pack(fill="both", expand=True)
        self.blist.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        self.blist.tree.bind("<Double-Button-1>", lambda e: self.edit_batch())
        bar = tk.Frame(left, background=theme.FACE)
        bar.pack(fill="x", pady=theme.px(4))
        for i, (text, cmd) in enumerate((("Добавить…", self.add_batch), ("Изменить…", self.edit_batch),
                                         ("Удалить", self.del_batch))):
            ttk.Button(bar, text=text, width=-6, command=cmd).grid(row=0, column=i, sticky="we", padx=theme.px(2))
            bar.grid_columnconfigure(i, weight=1)
        ttk.Button(bar, text="Структура — свойства…", command=app.open_structure).grid(
            row=1, column=0, columnspan=3, sticky="we", padx=theme.px(2), pady=(theme.px(4), 0))
        ttk.Button(bar, text="Экспорт базы в Excel…", command=app.export_db).grid(
            row=2, column=0, columnspan=3, sticky="we", padx=theme.px(2), pady=(theme.px(4), 0))

        right = tk.Frame(pw, background=theme.FACE)
        pw.add(right, weight=3)
        self.title = PanelTitle(right, "Партия не выбрана")
        self.title.pack(fill="x")
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)

        # карточка партии
        card = tk.Frame(self.nb, background=theme.FACE)
        self.nb.add(card, text="Карточка")
        self.card = Table(card, [("Значение", 60, "w")], height=10, tree_col=("Поле", 26))
        self.card.pack(fill="x", padx=theme.px(2), pady=theme.px(4))
        cbar = tk.Frame(card, background=theme.FACE)
        cbar.pack(fill="x")
        ttk.Button(cbar, text="Изменить карточку…", command=self.edit_batch, default="active").pack(
            side="left", padx=theme.px(4))
        self.todo = NoteBox(card, "", title="Нужно уточнить:")
        self.mods = groupbox(card, "Сводка по измерениям партии (среднее)")
        self.mods.pack(fill="both", expand=True, padx=theme.px(2), pady=theme.px(4))
        self.mods_text = tk.Label(self.mods, justify="left", anchor="nw")
        self.mods_text.pack(fill="both", expand=True)

        # измерения
        meas = tk.Frame(self.nb, background=theme.FACE)
        self.nb.add(meas, text="Измерения")
        mbar = tk.Frame(meas, background=theme.FACE)
        mbar.pack(fill="x", pady=theme.px(4))
        ttk.Button(mbar, text="Удалить измерение из базы", command=self.del_meas).pack(side="left", padx=theme.px(4))
        tk.Label(mbar, text="Измерения добавляются автоматически при открытии файлов.",
                 foreground=theme.SHADOW).pack(side="left", padx=theme.px(8))
        self.meas = Table(meas, [("Измерение", 12, "w"), ("Дата", 15, "w"), ("Файл", 16, "w"),
                                 ("Обскур., %", 9, "e"), ("d10", 7, "e"), ("d50", 7, "e"), ("d90", 7, "e"),
                                 ("D[3,2]", 7, "e"), ("SSA, м²/г", 9, "e"), ("Мелкая поп., %", 12, "e"),
                                 ("Флаги", 30, "w")], height=10)
        self.meas.pack(fill="both", expand=True)
        self.meas_ids: list[int] = []

        self.panels = {}
        for table in ("sem", "xrd", "chem", "print_jobs", "mech_tests"):
            p = CrudPanel(self.nb, self, table)
            self.nb.add(p, text=db.TABLE_TITLES[table])
            self.panels[table] = p
        self.path_label = tk.Label(right, anchor="w", foreground=theme.SHADOW)
        self.path_label.pack(fill="x", padx=theme.px(4))

    @property
    def conn(self):
        return self.app.db

    # ---------- обновление
    def refresh(self, keep=True):
        import re

        if not self._sash_set and self.winfo_ismapped():
            # правая часть с широкими таблицами иначе «отнимает» ширину у списка партий
            self.update_idletasks()
            self._pw.sashpos(0, theme.px(380))
            self._sash_set = True

        cur = self.batch_id if keep else None
        if self.app.current is not None and keep and getattr(self, "_follow", True):
            row = self.conn.execute("SELECT id FROM batches WHERE name=?", (self.app.current.name,)).fetchone()
            if row:
                cur = row["id"]
        nat = lambda s: [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", s)]  # noqa: E731
        rows = sorted(db.batches(self.conn), key=lambda r: nat(r["name"]))
        self.batch_ids = [r["id"] for r in rows]
        self.blist.fill([(r["name"], r["state"] or "", r["additive"] or "", c(r["additive_wt_pct"], 1),
                          r["n_meas"]) for r in rows])
        self.path_label.configure(text=f"Файл базы: {self.app.db_path}")
        if cur in self.batch_ids:
            iid = self.blist.tree.get_children()[self.batch_ids.index(cur)]
            self.blist.tree.selection_set(iid)
            self.blist.tree.see(iid)
        elif self.batch_ids and cur is None and keep is not None:
            self.blist.tree.selection_set(self.blist.tree.get_children()[0])
        self.on_select()

    def select_name(self, name: str):
        row = self.conn.execute("SELECT id FROM batches WHERE name=?", (name,)).fetchone()
        if row and row["id"] in getattr(self, "batch_ids", []):
            iid = self.blist.tree.get_children()[self.batch_ids.index(row["id"])]
            self.blist.tree.selection_set(iid)
            self.blist.tree.see(iid)

    def on_select(self):
        self._follow = False
        self.after_idle(lambda: setattr(self, "_follow", True))
        sel = self.blist.tree.selection()
        self.batch_id = self.batch_ids[self.blist.tree.index(sel[0])] if sel else None
        b = db.get(self.conn, "batches", self.batch_id) if self.batch_id else None
        self.title.configure(text=f"Партия: {b['name']}" if b else "Партия не выбрана")
        g = lambda v: f"{v:g}".replace(".", ",") if isinstance(v, float) else ("" if v is None else str(v))  # noqa: E731
        comp = ""
        if b and b["composition"]:
            cj = json.loads(b["composition"])
            adds = ", ".join(f"{k} {v:g} мас.%" for k, v in cj.get("additives_wt_pct", {}).items())
            comp = (f"{cj.get('formula', '')} ({'ат.%' if cj.get('basis') == 'at' else 'мас.%'})"
                    + (f" + {adds}" if adds else "")
                    + f"; ρ по правилу смесей {cj.get('rho_rule_of_mixtures', 0):.3f} г/см³".replace(".", ","))
        self.card.fill([(g(b[f.key]) if b else "",) for f in db.FIELDS["batches"]] + [(comp,)],
                       texts=[f.label for f in db.FIELDS["batches"]] + ["Состав (калькулятор плотности)"])
        notes = (b["notes"] or "") if b else ""
        if "уточнить" in notes:
            self.todo.set(notes.split("уточнить:", 1)[-1].strip() if notes.startswith("уточнить:") else notes)
            self.todo.pack(fill="x", padx=theme.px(2), pady=theme.px(4), before=self.mods)
        else:
            self.todo.pack_forget()
        ms = db.batch_measurements(self.conn, self.batch_id) if b else []
        self.meas_ids = [m["id"] for m in ms]
        self.meas.fill([(m["meas_no"], m["date"] or "", Path(m["file"] or "").name, c(m["obscuration"], 0),
                         c(m["d10"]), c(m["d50"]), c(m["d90"]), c(m["d32"]), c(m["ssa_m2_g"], 3),
                         c(m["fine_pop_pct"], 1), "; ".join(f"{lv}: {t}" for lv, t in json.loads(m["flags"] or "[]")))
                        for m in ms])
        self.mods_text.configure(text=self._summary(ms))
        for p in self.panels.values():
            p.refresh()

    def _summary(self, ms) -> str:
        if not ms:
            return "Нет измерений."

        def mean(k):
            v = [m[k] for m in ms if m[k] is not None]
            return sum(v) / len(v) if v else None

        lines = [f"Измерений: {len(ms)}",
                 f"d10 / d50 / d90: {c(mean('d10'))} / {c(mean('d50'))} / {c(mean('d90'))} мкм",
                 f"D[3,2]: {c(mean('d32'))} мкм;  удельная поверхность: {c(mean('ssa_m2_g'), 3)} м²/г "
                 "(нижняя оценка для сфер)"]
        fp = mean("fine_pop_pct")
        if fp is not None:
            lines.append(f"Мелкая популяция: {c(fp, 1)} %")
        return "\n".join(lines)

    def changed(self):
        self.refresh()

    # ---------- партии
    def add_batch(self):
        vals = RecordDialog(self, self.conn, "batches", "Новая партия").show()
        if vals:
            try:
                db.insert(self.conn, "batches", vals)
            except Exception as e:  # noqa: BLE001 — например, имя уже есть
                messagebox.showerror("База данных", f"Не удалось добавить партию: {e}", parent=self)
                return
            self.refresh()

    def edit_batch(self):
        if not self.batch_id:
            return
        row = dict(db.get(self.conn, "batches", self.batch_id))
        vals = RecordDialog(self, self.conn, "batches", f"Партия «{row['name']}»", values=row).show()
        if vals:
            try:
                db.update(self.conn, "batches", self.batch_id, vals)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("База данных", f"Не удалось сохранить: {e}", parent=self)
                return
            self.refresh()

    def del_batch(self):
        if not self.batch_id:
            return
        b = db.get(self.conn, "batches", self.batch_id)
        if messagebox.askyesno("Удаление партии", f"Удалить партию «{b['name']}» вместе со всеми её измерениями, "
                               "снимками, анализами, режимами печати и испытаниями?\n\nЭто нельзя отменить.",
                               icon="warning", parent=self):
            db.delete(self.conn, "batches", self.batch_id)
            self.batch_id = None
            self.refresh(keep=False)

    def del_meas(self):
        sel = self.meas.tree.selection()
        if not sel:
            return
        mid = self.meas_ids[self.meas.tree.index(sel[0])]
        if messagebox.askyesno("Удаление", "Удалить измерение из базы? (Файл на диске не трогается; при "
                               "следующем открытии файла оно импортируется снова.)", parent=self):
            db.delete_measurement(self.conn, mid)
            self.refresh()
