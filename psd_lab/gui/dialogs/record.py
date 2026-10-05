"""Форма-диалог «Добавить / Изменить» для записи любой таблицы базы (по описанию полей db.FIELDS)."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core import db
from .. import theme
from ..widgets import Dialog


class RecordDialog(Dialog):
    def __init__(self, parent, conn, table: str, title: str, values=None, batch_id=None):
        super().__init__(parent, title)
        self.conn, self.table, self.batch_id = conn, table, batch_id
        self.fields = db.FIELDS[table]
        self.widgets = {}
        values = dict(values or {})
        b = self.body
        self.jobs = {}
        for i, f in enumerate(self.fields):
            tk.Label(b, text=f.label + (" *" if f.required else "") + ":", anchor="w").grid(
                row=i, column=0, sticky="nw", padx=(0, theme.px(8)), pady=theme.px(2))
            v = values.get(f.key)
            if f.kind == "memo":
                w = tk.Text(b, width=46, height=4, wrap="word", relief="sunken", borderwidth=2)
                if v:
                    w.insert("1.0", str(v))
                w.grid(row=i, column=1, columnspan=2, sticky="we", pady=theme.px(2))
            elif f.kind in ("choice", "printjob"):
                if f.kind == "printjob":
                    jobs = conn.execute("SELECT id, process, machine, power_W FROM print_jobs WHERE batch_id=? "
                                        "ORDER BY id", (batch_id,)).fetchall()
                    self.jobs = {f"#{j['id']} {j['process'] or ''} {j['machine'] or ''} "
                                 f"{'' if j['power_W'] is None else f'{j[3]:g} Вт'}".strip(): j["id"] for j in jobs}
                    opts = list(self.jobs)
                    cur = next((k for k, jid in self.jobs.items() if jid == v), opts[0] if opts else "")
                    state = "readonly"
                else:
                    opts = list(f.choices)
                    cur = "" if v is None else str(v)
                    state = "normal" if table == "batches" else "readonly"
                w = ttk.Combobox(b, values=opts, state=state, width=28, font=theme.FONTS["ui"])
                w.set(cur)
                w.grid(row=i, column=1, sticky="w", pady=theme.px(2))
            else:
                w = tk.Entry(b, width=48 if f.kind in ("text", "file", "image") else 14)
                if v is not None:
                    w.insert(0, f"{v:g}".replace(".", ",") if isinstance(v, float) else str(v))
                w.grid(row=i, column=1, sticky="we" if f.kind in ("text", "file", "image") else "w",
                       pady=theme.px(2))
                if f.kind in ("file", "image"):
                    ttk.Button(b, text="Обзор…", width=-8, command=lambda w=w, f=f: self.browse(w, f)).grid(
                        row=i, column=2, padx=(theme.px(6), 0))
            self.widgets[f.key] = w
        if table == "print_jobs":
            tk.Label(b, text="Плотность энергии E = P / (v·h·t) считается автоматически.\n"
                     "Одна E не определяет качество: при той же E разные P и v дают разный\n"
                     "результат (Bertoli et al., Materials & Design, 2017).",
                     foreground=theme.SHADOW, justify="left").grid(row=len(self.fields), column=0, columnspan=3, sticky="w",
                                                   pady=(theme.px(6), 0))
        if table == "mech_tests" and not self.jobs:
            tk.Label(b, text="Сначала добавьте режим печати на вкладке «Печать».", foreground="#FF0000").grid(
                row=len(self.fields), column=0, columnspan=3, sticky="w")
        b.grid_columnconfigure(1, weight=1)

    def browse(self, entry, f):
        types = [("Изображения", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif")] if f.kind == "image" else []
        p = filedialog.askopenfilename(parent=self, title=f.label, filetypes=types + [("Все файлы", "*.*")])
        if p:
            entry.delete(0, "end")
            entry.insert(0, p)

    def values(self) -> dict:
        out = {}
        for f in self.fields:
            w = self.widgets[f.key]
            if f.kind == "memo":
                out[f.key] = w.get("1.0", "end").strip()
            elif f.kind == "printjob":
                out[f.key] = self.jobs.get(w.get())
            else:
                out[f.key] = w.get()
        return out

    def on_ok(self):
        try:
            db.coerce(self.table, self.values())
        except ValueError as e:
            messagebox.showerror(self.title(), str(e), parent=self)
            return
        self.result = self.values()
        self.destroy()
