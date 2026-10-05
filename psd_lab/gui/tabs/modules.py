"""Вкладки модулей М2 (Популяции), М3+М4 (Технология), М5 (Поверхность)."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...core import deconv, surface, windows
from ...core.metrics import d32
from ...core.plots import draw_populations, draw_sieve, draw_surface, draw_tech_bars
from .. import theme
from ..widgets import NoteBox, PanelTitle, ReadoutBar, Table, groupbox, sunken
from .plot_panel import PlotPanel

M2_HINT = ("доля мелкой популяции у П/С (30–80 %) на порядок больше объёмной доли добавки "
           "(0,5–1,5 мас.% ≈ 1–3 об.%), значит мелкая мода — не сама добавка. Её происхождение "
           "(агломераты? продукт обработки?) надо проверять СЭМ и измерением с разной мощностью ультразвука.")
M2_ASSUMPTIONS = ("каждая популяция описывается логнормальным законом; число компонент выбрано по BIC; "
                  "популяции — группы компонент между провалами плотности. Субмикронный «горб» (< 1 мкм) "
                  "может быть артефактом расчёта по Фраунгоферу.")


def c(v, nd=1):
    return "—" if v is None or v != v else f"{v:.{nd}f}".replace(".", ",")


def _empty(panel, text):
    panel.figure.clear()
    ax = panel.figure.add_subplot(111)
    ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=11, color="#808080")
    panel.draw()


# ==================================================================== М2
class PopulationsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, background=theme.FACE)
        self.app = app
        pw = ttk.PanedWindow(self, orient="vertical")
        pw.pack(fill="both", expand=True)
        self.plot = PlotPanel(pw, "Популяции частиц", on_save=self.save_png)
        pw.add(self.plot, weight=3)

        low = tk.Frame(pw, background=theme.FACE)
        pw.add(low, weight=2)
        row = tk.Frame(low, background=theme.FACE)
        row.pack(fill="both", expand=True)
        g1 = groupbox(row, "Популяции (по провалам плотности)")
        g1.pack(side="left", fill="both", expand=True, padx=(theme.px(2), theme.px(4)))
        self.pops = Table(g1, [("Популяция", 13, "w"), ("Доля, %", 8, "e"), ("Мода, мкм", 9, "e"),
                               ("Диапазон, мкм", 14, "center")], height=4)
        self.pops.pack(fill="both", expand=True)
        g2 = groupbox(row, "Логнормальные компоненты (число — по BIC)")
        g2.pack(side="left", fill="both", expand=True, padx=(0, theme.px(2)))
        self.comps = Table(g2, [("Тип", 13, "w"), ("Доля, %", 8, "e"), ("Медиана, мкм", 11, "e"),
                                ("σg", 6, "e"), ("Показ", 12, "w")], height=4)
        self.comps.pack(fill="both", expand=True)
        self.info = tk.Label(low, anchor="w", justify="left")
        self.info.pack(fill="x", padx=theme.px(4), pady=(theme.px(4), 0))
        self.hint = NoteBox(low, M2_HINT, title="Подсказка:")
        self.hint.pack(fill="x", padx=theme.px(2), pady=(theme.px(4), 0))
        self.assume = NoteBox(low, M2_ASSUMPTIONS)
        self.assume.pack(fill="x", padx=theme.px(2), pady=(theme.px(4), theme.px(2)))
        self.res = None

    def refresh(self):
        s = self.app.current
        if s is None:
            _empty(self.plot, "Выберите образец слева")
            self.plot.set_title("Популяции частиц")
            return
        self.app.busy(True)
        try:
            res = deconv.fit(s)
        finally:
            self.app.busy(False)
        self.res = res
        lang = self.app.st.lang
        self._draw = lambda fig, fs=1.0: draw_populations(fig, s, res, lang=lang, font_scale=fs)
        self._name = f"популяции_{s.name}"
        self._draw(self.plot.figure, 0.9)
        self.plot.set_title(f"Популяции частиц — {s.label}")
        self.plot.draw()
        self.pops.fill([(p.kind, c(p.weight_pct), c(p.mode_um, 2),
                         f"{c(p.lo_um, 0) if p.lo_um else '0'} – {c(p.hi_um, 0) if p.hi_um else '…'}")
                        for p in res.populations])
        self.comps.fill([(x.kind, c(x.weight_pct), c(x.median_um, 2), c(x.sigma_g, 2),
                          "да" if x.shown else "нет (< 3 %)") for x in res.components])
        bic = ", ".join(f"K={k}: {v:.0f}" for k, v in sorted(res.bic.items()))
        self.info.configure(text=f"R² по накопленной кривой = {res.r2:.4f}".replace(".", ",")
                            + f"     Компонент: {res.k} (BIC: {bic})")

    def save_png(self):
        if getattr(self, "_draw", None) and self.app.current is not None:
            self.app.save_figure_png(self._draw, self._name)


# ==================================================================== М3 + М4
class TechTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, background=theme.FACE)
        self.app = app
        st = app.st
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        # ---------- окна СЛС / СЭЛС
        t1 = tk.Frame(self.nb, background=theme.FACE)
        self.nb.add(t1, text="Окна СЛС / СЭЛС")
        ctl = tk.Frame(t1, background=theme.FACE)
        ctl.pack(fill="x", pady=theme.px(4))
        tk.Label(ctl, text="Окно СЛС, мкм:").pack(side="left", padx=(theme.px(4), theme.px(4)))
        self.sls = ttk.Combobox(ctl, state="readonly", width=10, font=theme.FONTS["ui"],
                                values=[f"{a:g}–{b:g}" for a, b in st.sls_windows])
        self.sls.current(min(st.sls_index, len(st.sls_windows) - 1))
        self.sls.pack(side="left")
        tk.Label(ctl, text="Окно СЭЛС, мкм:").pack(side="left", padx=(theme.px(16), theme.px(4)))
        self.ebm = ttk.Combobox(ctl, state="readonly", width=10, font=theme.FONTS["ui"],
                                values=[f"{a:g}–{b:g}" for a, b in st.ebm_windows])
        self.ebm.current(min(st.ebm_index, len(st.ebm_windows) - 1))
        self.ebm.pack(side="left")
        for cb in (self.sls, self.ebm):
            cb.bind("<<ComboboxSelected>>", lambda e: self.on_windows())

        pw = ttk.PanedWindow(t1, orient="vertical")
        pw.pack(fill="both", expand=True)
        self.bars = PlotPanel(pw, "Доли по окнам печати (все выбранные образцы)", on_save=self.save_bars)
        pw.add(self.bars, weight=3)
        low = tk.Frame(pw, background=theme.FACE)
        pw.add(low, weight=2)
        g = groupbox(low, "Выбранный образец")
        g.pack(fill="both", expand=True, padx=theme.px(2))
        self.facts = tk.Label(g, anchor="w", justify="left", font=theme.FONTS["ui"])
        self.facts.pack(fill="x")
        self.pop_table = Table(g, [("Популяция", 13, "w"), ("в окне СЛС, % популяции", 20, "e"),
                                   ("в окне СЭЛС, % популяции", 20, "e")], height=3)
        self.pop_table.pack(fill="both", expand=True, pady=(theme.px(4), 0))
        self.note = NoteBox(low, windows.TECH_NOTE.replace("Справка (проверить по источникам): ", ""),
                            title="Справка (проверить по источникам):")
        self.note.pack(fill="x", padx=theme.px(2), pady=theme.px(4))

        # ---------- выход годного
        t2 = tk.Frame(self.nb, background=theme.FACE)
        self.nb.add(t2, text="Выход годного после рассева")
        ctl = tk.Frame(t2, background=theme.FACE)
        ctl.pack(fill="x", pady=theme.px(4))
        tk.Label(ctl, text="Окно рассева: от").pack(side="left", padx=(theme.px(4), theme.px(4)))
        self.lo = tk.Entry(ctl, width=6)
        self.lo.insert(0, f"{st.sieve_window[0]:g}")
        self.lo.pack(side="left")
        tk.Label(ctl, text="до").pack(side="left", padx=theme.px(4))
        self.hi = tk.Entry(ctl, width=6)
        self.hi.insert(0, f"{st.sieve_window[1]:g}")
        self.hi.pack(side="left")
        tk.Label(ctl, text="мкм").pack(side="left", padx=theme.px(4))
        ttk.Button(ctl, text="Пересчитать", command=self.on_sieve, default="active").pack(side="left", padx=theme.px(8))
        for e in (self.lo, self.hi):
            e.bind("<Return>", lambda ev: self.on_sieve())

        self.req_note = NoteBox(t2, windows.REQ_NOTE + " " + windows.SIEVE_NOTE)
        self.req_note.pack(side="bottom", fill="x", padx=theme.px(2), pady=theme.px(4))
        top = tk.Frame(t2, background=theme.FACE)
        top.pack(fill="x")
        self.yield_bar = ReadoutBar(top, "Результат рассева")
        self.yield_bar.pack(side="left", fill="y", anchor="n")
        self.yield_bar.set_fields(["Годное, %", "Мелочь, %", "Крупное, %", "Из 1 кг, г"])
        g = groupbox(top, "Требования к порошку и фактические значения")
        g.pack(side="left", fill="both", expand=True, padx=theme.px(2), pady=(0, theme.px(2)))
        self.req_frame = sunken(g)
        self.req_frame.configure(background=theme.FIELD)
        self.req_frame.pack(fill="x")
        self.sieve_plot = PlotPanel(t2, "Кривая после классификации (модель)", on_save=self.save_sieve)
        self.sieve_plot.pack(fill="both", expand=True)

    # ---------- обработчики
    def on_windows(self):
        self.app.st.sls_index, self.app.st.ebm_index = self.sls.current(), self.ebm.current()
        self.refresh()

    def on_sieve(self):
        try:
            lo, hi = float(self.lo.get().replace(",", ".")), float(self.hi.get().replace(",", "."))
            if not 0 <= lo < hi:
                raise ValueError
        except ValueError:
            messagebox.showerror("Окно рассева", "Введите границы окна: от меньшего к большему, в мкм.",
                                 parent=self)
            return
        self.app.st.sieve_window = [lo, hi]
        self.refresh()

    def refresh(self):
        st = self.app.st
        sls, ebm = st.sls, st.ebm
        en = self.app.enabled_samples()
        self._draw_bars = lambda fig, fs=1.0: draw_tech_bars(fig, en, sls, ebm, font_scale=fs)
        self._draw_bars(self.bars.figure, 0.9)
        self.bars.draw()
        s = self.app.current
        if s is None:
            self.facts.configure(text="Выберите образец слева.")
            self.pop_table.fill([])
            _empty(self.sieve_plot, "Выберите образец слева")
            return
        self.facts.configure(text=f"{s.label}: " + windows.facts_text(s, sls, ebm))
        res = deconv.fit(s)
        rows = windows.population_windows(res.main_populations, [sls, ebm])
        self.pop_table.fill([(k, c(a), c(b)) for k, (a, b) in rows])

        lo, hi = st.sieve_window
        sv = windows.sieve(s, lo, hi)
        self.yield_bar.set_values([c(sv.yield_pct), c(sv.fines_pct), c(sv.coarse_pct), f"{sv.grams_per_kg():.0f}"])
        self._fill_requirements(s, sv)
        lang = st.lang
        self._draw_sieve = lambda fig, fs=1.0: draw_sieve(fig, s, sv, lang=lang, font_scale=fs)
        self._sieve_name = f"рассев_{lo:g}-{hi:g}_{s.name}"
        self._draw_sieve(self.sieve_plot.figure, 0.9)
        self.sieve_plot.set_title(f"Кривая после рассева {lo:g}–{hi:g} мкм — модель идеального рассева — {s.label}")
        self.sieve_plot.draw()

    def _fill_requirements(self, s, sv):
        f = self.req_frame
        for w in f.winfo_children():
            w.destroy()
        req = self.app.st.requirements
        before = windows.requirements_check(s, req)
        after = windows.requirements_check(sv.sieved, req)
        heads = ["Параметр", "Требование", "Исходный", "", "После рассева", ""]
        for j, h in enumerate(heads):
            tk.Label(f, text=h, relief="raised", borderwidth=2, background=theme.FACE, padx=theme.px(6)).grid(
                row=0, column=j, sticky="nsew")
        ok, bad = theme.load_icon(self, "ok"), theme.load_icon(self, "cross")
        for i, (b, a) in enumerate(zip(before, after), start=1):
            vals = [b.name, b.requirement, c(b.value, 2), None, c(a.value, 2), None]
            for j, v in enumerate(vals):
                if v is None:
                    good = (b if j == 3 else a).ok
                    tk.Label(f, image=ok if good else bad, background=theme.FIELD).grid(row=i, column=j, padx=theme.px(4))
                else:
                    tk.Label(f, text=v, background=theme.FIELD, anchor="e" if j in (2, 4) else "w",
                             padx=theme.px(6), pady=theme.px(2)).grid(row=i, column=j, sticky="we")
        for j in range(len(heads)):
            f.grid_columnconfigure(j, weight=1 if j in (0, 1) else 0)

    def save_bars(self):
        if getattr(self, "_draw_bars", None):
            self.app.save_figure_png(self._draw_bars, "окна_СЛС_СЭЛС")

    def save_sieve(self):
        if getattr(self, "_draw_sieve", None) and self.app.current is not None:
            self.app.save_figure_png(self._draw_sieve, self._sieve_name)


# ==================================================================== М5
class SurfaceTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, background=theme.FACE)
        self.app = app
        self.read = ReadoutBar(self, "Удельная поверхность (выбранный образец)")
        self.read.pack(fill="x", side="top")
        self.read.set_fields(["SSA, м²/г", "D[3,2], мкм", "ρ, г/см³"])
        self.headline = tk.Label(self, font=theme.FONTS["big"], anchor="w", foreground=theme.SELECT_BG)
        self.headline.pack(fill="x", padx=theme.px(6), pady=theme.px(2))
        pw = ttk.PanedWindow(self, orient="vertical")
        pw.pack(fill="both", expand=True)
        self.plot = PlotPanel(pw, "Доля объёма и доля поверхности по фракциям", on_save=self.save_png)
        pw.add(self.plot, weight=3)
        low = tk.Frame(pw, background=theme.FACE)
        pw.add(low, weight=2)
        g = groupbox(low, "Все выбранные образцы")
        g.pack(fill="both", expand=True, padx=theme.px(2))
        self.table = Table(g, [("Образец", 22, "w"), ("D[3,2], мкм", 11, "e"), ("SSA, м²/г", 10, "e"),
                               ("< 15 мкм: объём, %", 16, "e"), ("< 15 мкм: поверхность, %", 20, "e")], height=5)
        self.table.pack(fill="both", expand=True)
        self.note = NoteBox(low, surface.ASSUMPTIONS.replace("Допущения: ", ""))
        self.note.pack(fill="x", padx=theme.px(2), pady=theme.px(4))

    def refresh(self):
        st = self.app.st
        rho = st.density_g_cm3
        rows = []
        for s in self.app.enabled_samples():
            v, a = surface.fine_shares(s)
            rows.append((s.label, c(d32(s), 2), c(surface.ssa_m2_g(s, rho), 3), c(v), c(a)))
        self.table.fill(rows)
        s = self.app.current
        if s is None:
            self.read.set_values(["—", "—", c(rho, 2)])
            self.headline.configure(text="")
            _empty(self.plot, "Выберите образец слева")
            return
        self.read.set_values([c(surface.ssa_m2_g(s, rho), 3), c(d32(s), 2), c(rho, 2)])
        self.headline.configure(text=f"{s.name}: {surface.headline(s)}")
        rows = surface.shares(s, st.windows)
        self._draw = lambda fig, fs=1.0: draw_surface(fig, rows, font_scale=fs)
        self._name = f"поверхность_{s.name}"
        self._draw(self.plot.figure, 0.9)
        self.plot.set_title(f"Доля объёма и доля поверхности по фракциям — {s.label}")
        self.plot.draw()

    def save_png(self):
        if getattr(self, "_draw", None) and self.app.current is not None:
            self.app.save_figure_png(self._draw, self._name)

