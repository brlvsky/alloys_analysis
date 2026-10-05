"""Сервис → Плотность состава (М7)."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...core import db, density
from .. import theme
from ..widgets import NoteBox, ReadoutBar, Table, center_on, groupbox


def c(v, nd=2):
    return "—" if v is None else f"{v:.{nd}f}".replace(".", ",")


class DensityWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Плотность состава")
        self.configure(background=theme.FACE)
        self.transient(app.root)
        body = tk.Frame(self, background=theme.FACE, padx=theme.px(10), pady=theme.px(8))
        body.pack(fill="both", expand=True)

        g = groupbox(body, "Состав сплава")
        g.pack(fill="x")
        tk.Label(g, text="Пресет:").grid(row=0, column=0, sticky="w")
        self.preset = ttk.Combobox(g, values=list(density.PRESETS), state="readonly", width=28, font=theme.FONTS["ui"])
        self.preset.grid(row=0, column=1, sticky="w", padx=theme.px(6))
        self.preset.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())
        tk.Label(g, text="Состав:").grid(row=1, column=0, sticky="w", pady=(theme.px(6), 0))
        self.formula = tk.Entry(g, width=40)
        self.formula.grid(row=1, column=1, columnspan=3, sticky="we", padx=theme.px(6), pady=(theme.px(6), 0))
        tk.Label(g, text="первый элемент — основа, например Ti-43.5Al-4Nb-1Mo-0.1B", foreground=theme.SHADOW).grid(
            row=2, column=1, columnspan=3, sticky="w", padx=theme.px(6))
        self.basis = tk.StringVar(value="at")
        tk.Radiobutton(g, text="ат.%", variable=self.basis, value="at").grid(row=1, column=4, sticky="w")
        tk.Radiobutton(g, text="мас.%", variable=self.basis, value="wt").grid(row=1, column=5, sticky="w")

        a = groupbox(body, "Добавки поверх сплава, мас.%  и измеренная плотность")
        a.pack(fill="x", pady=theme.px(6))
        self.add = {}
        for i, el in enumerate(density.ADDITIVES):
            tk.Label(a, text=f"{el}:").grid(row=0, column=2 * i, sticky="e", padx=(theme.px(8) if i else 0, theme.px(4)))
            e = tk.Entry(a, width=7)
            e.grid(row=0, column=2 * i + 1, sticky="w")
            self.add[el] = e
        tk.Label(a, text="Измеренная плотность, г/см³:").grid(row=1, column=0, columnspan=3, sticky="w",
                                                            pady=(theme.px(6), 0))
        self.measured = tk.Entry(a, width=8)
        self.measured.grid(row=1, column=3, sticky="w", pady=(theme.px(6), 0))
        tk.Label(a, text="(если заполнено — используется вместо оценки)", foreground=theme.SHADOW).grid(
            row=1, column=4, columnspan=3, sticky="w", padx=theme.px(6), pady=(theme.px(6), 0))
        ttk.Button(body, text="Рассчитать", command=self.calc, default="active").pack(anchor="e")

        self.read = ReadoutBar(body, "Результат")
        self.read.pack(fill="x", pady=(theme.px(6), 0))
        self.read.set_fields(["ρ (правило смесей), г/см³", "ρ для сравнения, г/см³", "Δ к Ti6Al4V, %"], )
        self.verdict = tk.Label(body, compound="left", anchor="w", font=theme.FONTS["bold"], padx=theme.px(4))
        self.verdict.pack(fill="x", pady=(theme.px(4), 0))
        self.caveat = tk.Label(body, anchor="w", justify="left", foreground="#800000", padx=theme.px(4),
                               wraplength=theme.px(640))
        self.caveat.pack(fill="x", pady=(0, theme.px(4)))
        self.table = Table(body, [("Элемент", 9, "w"), ("ат.%", 9, "e"), ("мас.%", 9, "e"), ("ρ, г/см³", 9, "e")],
                           height=7)
        self.table.pack(fill="both", expand=True)
        NoteBox(body, density.ASSUMPTIONS).pack(fill="x", pady=theme.px(6))

        s = groupbox(body, "Сохранить состав в карточку партии")
        s.pack(fill="x")
        names = [r["name"] for r in db.batches(app.db)]
        self.batch = ttk.Combobox(s, values=names, state="readonly", width=28, font=theme.FONTS["ui"])
        if app.current is not None and app.current.name in names:
            self.batch.set(app.current.name)
        self.batch.pack(side="left")
        ttk.Button(s, text="Сохранить", command=self.save).pack(side="left", padx=theme.px(6))
        ttk.Button(s, text="Закрыть", command=self.destroy).pack(side="right")
        self.bind("<Return>", lambda e: self.calc())

        self.preset.current(0)
        self.apply_preset()
        self.geometry(f"{theme.px(760)}x{theme.px(720)}")
        center_on(self, app.root)

    def apply_preset(self):
        f, basis = density.PRESETS[self.preset.get()]
        self.formula.delete(0, "end")
        self.formula.insert(0, f)
        self.basis.set(basis)
        self.calc()

    def _num(self, e):
        t = e.get().strip().replace(",", ".")
        return float(t) if t else None

    def calc(self):
        try:
            adds = {k: self._num(e) for k, e in self.add.items()}
            meas = self._num(self.measured)
            self.res = density.calculate(self.formula.get(), self.basis.get(), adds, meas)
        except ValueError as e:
            messagebox.showerror("Плотность состава", f"Проверьте состав: {e}", parent=self)
            return
        r = self.res
        self.read.set_values([c(r.rho_estimate, 3), c(r.rho, 3), c(r.delta_pct, 1)])
        ok = r.in_target
        src = "измеренной плотности" if r.rho_measured else "оценке по правилу смесей"
        self.verdict.configure(
            image=theme.load_icon(self, "ok" if ok else "cross"),
            text=f"  По {src}: {'в цели' if ok else 'вне цели'} ТЗ (легче Ti6Al4V на 10–15 %: ρ = 3,77–3,99 г/см³)",
            foreground="#008000" if ok else "#FF0000")
        self.caveat.configure(text="" if r.rho_measured else
                              "Осторожно: для γ-TiAl правило смесей обычно занижает плотность на несколько процентов, "
                              "поэтому вывод о цели ТЗ делайте по измеренной плотности (гидростатическое взвешивание "
                              "или пикнометрия).")
        rows = [(el, c(r.at.get(el), 3), c(r.wt.get(el), 3), c(density.ELEMENTS[el][1], 3)) for el in r.wt]
        self.table.fill(rows)

    def save(self):
        name = self.batch.get()
        if not name or not hasattr(self, "res"):
            return
        bid = self.app.db.execute("SELECT id FROM batches WHERE name=?", (name,)).fetchone()["id"]
        r = self.res
        comp = {"formula": self.formula.get(), "basis": self.basis.get(),
                "additives_wt_pct": {k: self._num(e) for k, e in self.add.items() if self._num(e)},
                "wt_pct": {k: round(v, 4) for k, v in r.wt.items()},
                "rho_rule_of_mixtures": round(r.rho_estimate, 4)}
        db.save_composition(self.app.db, bid, comp, r.rho_measured)
        self.app.log(f"Состав {self.formula.get()} сохранён в карточку партии «{name}»")
        messagebox.showinfo("Плотность состава", f"Состав сохранён в карточку партии «{name}».", parent=self)
