"""Вкладка «Шихта» (версия 1.1): состав → навески по загрузкам барабана.

Группы: «Состав», «Добавки», «Партия (загрузки)», «Лигатура», «Результат». Считается сразу при изменении
любого поля; ошибки ввода — красной строкой в «Результате» и в строке состояния, без всплывающих окон на
каждый символ (всплывающее окно — только при экспорте и по кнопке «Проверить»).
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ... import APP_NAME
from ...core import charge, charge_report
from ...core.charge import Additive, ChargeError, Recipe, fmt_g, fmt_pct
from .. import theme
from ..widgets import HelpTip, NoteBox, PanelTitle, Table, groupbox

UNIT_CHOICES = {"at": "ат.%", "wt": "мас.%", "mol": "мол.%"}
MODE_CHOICES = {"instead": "за счёт", "over": "сверх"}
VARIANT_MODES = {"each": "каждая добавка отдельно", "all": "все добавки вместе", "both": "и так, и так"}
LOAD_MODES = {"full": "полные загрузки (по ёмкости барабана)", "equal": "равные загрузки"}
LIG_MODES = {"none": "не использовать", "computed": "рассчитать лигатуру", "given": "лигатура задана"}


def _num(entry: tk.Entry, default=None, name="значение"):
    t = (entry.get() or "").strip().replace(",", ".")
    if not t:
        if default is None:
            raise ChargeError(f"{name}: пустое поле")
        return default
    try:
        return float(t)
    except ValueError as e:
        raise ChargeError(f"{name}: «{entry.get()}» — не число") from e


class ChargeTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, background=theme.FACE)
        self.app = app
        self.result = None
        self._recipe_path: Path | None = None
        self._busy = False

        PanelTitle(self, "Расчёт шихты: состав → навески на загрузки барабана").pack(fill="x")
        self.note = NoteBox(self, "Допущения: " + charge.ASSUMPTIONS, title="")
        self.note.pack(side="bottom", fill="x", padx=theme.px(2), pady=theme.px(2))
        body = tk.Frame(self, background=theme.FACE)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, background=theme.FACE)
        left.pack(side="left", fill="y", padx=theme.px(2), pady=theme.px(2))
        right = tk.Frame(body, background=theme.FACE)
        right.pack(side="left", fill="both", expand=True, padx=(0, theme.px(2)), pady=theme.px(2))

        self._build_composition(left)
        self._build_additives(left)
        self._build_batch(left)
        self._build_ligature(left)
        self._build_result(right)

        self.load_example(quiet=True)

    # ---------------------------------------------------------------- ввод
    def _build_composition(self, parent):
        g = groupbox(parent, "Состав сплава")
        g.pack(fill="x")
        tk.Label(g, text="Сплав / партия:").grid(row=0, column=0, sticky="w")
        self.e_alloy = tk.Entry(g, width=34)
        self.e_alloy.grid(row=0, column=1, columnspan=2, sticky="we", pady=theme.px(1))
        tk.Label(g, text="Состав:").grid(row=1, column=0, sticky="w")
        self.e_comp = tk.Entry(g, width=34)
        self.e_comp.grid(row=1, column=1, columnspan=2, sticky="we", pady=theme.px(1))
        self.v_basis = tk.StringVar(value="at")
        f = tk.Frame(g, background=theme.FACE)
        f.grid(row=2, column=1, columnspan=2, sticky="w")
        for val, txt in (("at", "ат.%"), ("wt", "мас.%")):
            tk.Radiobutton(f, text=txt, value=val, variable=self.v_basis, command=self.recalc,
                           background=theme.FACE, activebackground=theme.FACE).pack(side="left")
        tk.Label(g, text="например: 50Ti-44Al-4,9Nb-1Mo-0,1B", foreground=theme.SHADOW).grid(
            row=3, column=0, columnspan=3, sticky="w")
        self.e_comp.bind("<KeyRelease>", lambda e: self.recalc())
        self.e_alloy.bind("<KeyRelease>", lambda e: self.recalc())
        HelpTip.static(self.e_comp, "Состав сплава",
                       "Пишите «число + элемент» через дефис. Элемент без числа — основа (остаток до 100 %). "
                       "Можно и соединения: 1CeO2. Точка и запятая — одинаково.")

    def _build_additives(self, parent):
        g = groupbox(parent, "Добавки")
        g.pack(fill="x", pady=(theme.px(4), 0))
        self.adds = Table(g, [("Компонент", 10, "w"), ("Кол-во", 7, "e"), ("Единицы", 8, "w"),
                              ("Как", 8, "w"), ("За счёт", 8, "w")], height=4)
        self.adds.pack(fill="x")
        self.adds.tree.bind("<Double-1>", lambda e: self.edit_additive())
        bar = tk.Frame(g, background=theme.FACE)
        bar.pack(fill="x", pady=(theme.px(2), 0))
        for txt, cmd in (("Добавить…", self.add_additive), ("Изменить…", self.edit_additive),
                         ("Удалить", self.del_additive)):
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=(0, theme.px(4)))
        self._adds: list[Additive] = []
        f = tk.Frame(g, background=theme.FACE)
        f.pack(fill="x", pady=(theme.px(3), 0))
        tk.Label(f, text="Считать:").pack(side="left")
        self.v_mode = tk.StringVar(value=VARIANT_MODES["both"])
        cb = ttk.Combobox(f, state="readonly", width=24, font=theme.FONTS["ui"],
                          values=list(VARIANT_MODES.values()), textvariable=self.v_mode)
        cb.pack(side="left", padx=theme.px(4))
        cb.bind("<<ComboboxSelected>>", lambda e: self.recalc())

    def _build_batch(self, parent):
        g = groupbox(parent, "Партия и загрузки")
        g.pack(fill="x", pady=(theme.px(4), 0))
        self.e_target = self._row(g, 0, "Нужно смеси, г:", "1500")
        self.e_cap = self._row(g, 1, "Ёмкость барабана, г:", "200")
        self.e_reserve = self._row(g, 2, "Запас на потери, %:", "0")
        self.e_balls = self._row(g, 3, "Шары : порошок (необяз.):", "")
        tk.Label(g, text="Режим:").grid(row=4, column=0, sticky="w")
        self.v_load = tk.StringVar(value=LOAD_MODES["full"])
        cb = ttk.Combobox(g, state="readonly", width=30, font=theme.FONTS["ui"],
                          values=list(LOAD_MODES.values()), textvariable=self.v_load)
        cb.grid(row=4, column=1, sticky="w", pady=theme.px(1))
        cb.bind("<<ComboboxSelected>>", lambda e: self.recalc())
        HelpTip.static(self.e_cap, "Ёмкость барабана",
                       "Сколько порошка помещается в один барабан мельницы за одну закладку.")
        HelpTip.static(self.e_balls, "Шары : порошок",
                       "Во сколько раз масса шаров больше массы порошка. Если задать, программа посчитает "
                       "массу шаров на загрузку.")

    def _row(self, g, row, label, default):
        tk.Label(g, text=label).grid(row=row, column=0, sticky="w")
        e = tk.Entry(g, width=10)
        e.insert(0, default)
        e.grid(row=row, column=1, sticky="w", pady=theme.px(1))
        e.bind("<KeyRelease>", lambda ev: self.recalc())
        return e

    def _build_ligature(self, parent):
        g = groupbox(parent, "Лигатура")
        g.pack(fill="x", pady=(theme.px(4), 0))
        self.v_lig = tk.StringVar(value=LIG_MODES["none"])
        cb = ttk.Combobox(g, state="readonly", width=24, font=theme.FONTS["ui"],
                          values=list(LIG_MODES.values()), textvariable=self.v_lig)
        cb.grid(row=0, column=0, columnspan=2, sticky="w", pady=theme.px(1))
        cb.bind("<<ComboboxSelected>>", lambda e: self.recalc())
        tk.Label(g, text="Чистыми вводятся:").grid(row=1, column=0, sticky="w")
        self.e_pure = tk.Entry(g, width=18)
        self.e_pure.grid(row=1, column=1, sticky="w")
        self.e_pure.bind("<KeyRelease>", lambda e: self.recalc())
        tk.Label(g, text="Состав лигатуры, мас.%:").grid(row=2, column=0, sticky="w")
        self.e_ligcomp = tk.Entry(g, width=18)
        self.e_ligcomp.grid(row=2, column=1, sticky="w")
        self.e_ligcomp.bind("<KeyRelease>", lambda e: self.recalc())
        HelpTip.static(self.e_pure, "Чистые компоненты",
                       "Какие порошки добавляются в чистом виде, а не в составе лигатуры (через запятую, "
                       "например Al). Остальное программа соберёт в лигатуру.")
        HelpTip.static(self.e_ligcomp, "Состав имеющейся лигатуры",
                       "Если лигатура уже есть, впишите её состав: «Ti 81,25; Nb 15,45; Mo 3,26; B 0,04». "
                       "Программа подберёт, сколько её и каких чистых порошков взять.")

    def _build_result(self, parent):
# кнопки в две строки: в одну они не помещаются на экране 1280 px
        bar = tk.Frame(parent, background=theme.FACE)
        bar.pack(fill="x")
        for txt, cmd in (("Загрузить пример", self.load_example), ("Проверить", self.check),
                         ("Бланк навесок…", self.export_blank), ("Excel…", self.export_xlsx)):
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=(0, theme.px(4)))
        self.v_perload = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="бланк по загрузкам", variable=self.v_perload, background=theme.FACE,
                       activebackground=theme.FACE).pack(side="left")
        bar2 = tk.Frame(parent, background=theme.FACE)
        bar2.pack(fill="x", pady=(theme.px(2), 0))
        for txt, cmd in (("Сохранить рецепт…", self.save_recipe), ("Открыть рецепт…", self.open_recipe),
                         ("В карточку партии…", self.save_to_batch)):
            ttk.Button(bar2, text=txt, command=cmd).pack(side="left", padx=(0, theme.px(4)))
        tk.Label(bar2, text="Навески:").pack(side="left", padx=(theme.px(8), theme.px(4)))
        self.v_variant = tk.StringVar()
        self.cb_variant = ttk.Combobox(bar2, state="readonly", width=24, font=theme.FONTS["ui"],
                                       textvariable=self.v_variant)
        self.cb_variant.pack(side="left")
        self.cb_variant.bind("<<ComboboxSelected>>", lambda e: self._show(self.result) if self.result else None)

        self.msg = tk.Label(parent, text="", anchor="w", justify="left", background=theme.FACE,
                            wraplength=theme.px(600))
        self.msg.pack(fill="x", pady=theme.px(2))
        self.msg.bind("<Configure>", lambda e: self.msg.configure(wraplength=max(theme.px(200),
                                                                                e.width - theme.px(8))))

        pw = ttk.PanedWindow(parent, orient="vertical")
        pw.pack(fill="both", expand=True)
        g = groupbox(pw, "Варианты состава, мас.%")
        pw.add(g, weight=3)
        self.t_var = Table(g, [("Вариант", 26, "w")], height=6, xscroll=True)
        self.t_var.pack(fill="both", expand=True)
        low = tk.Frame(pw, background=theme.FACE)
        pw.add(low, weight=2)
        g2 = groupbox(low, "Навеска на одну загрузку и на всю партию")
        g2.pack(side="left", fill="both", expand=True)
        self.t_load = Table(g2, [("Компонент", 12, "w"), ("На загрузку, г", 12, "e"),
                                 ("На всю партию, г", 14, "e"), ("Точность весов", 16, "w")], height=6)
        self.t_load.pack(fill="both", expand=True)
        g3 = groupbox(low, "Лигатура")
        g3.pack(side="left", fill="both", expand=True, padx=(theme.px(4), 0))
        self.t_lig = Table(g3, [("Что взять", 16, "w"), ("мас.%", 9, "e"), ("На загрузку, г", 13, "e")], height=6)
        self.t_lig.pack(fill="both", expand=True)

    # ---------------------------------------------------------------- добавки
    def _fill_adds(self):
        rows = [[a.component, fmt_pct(a.amount), UNIT_CHOICES.get(a.unit or "", "?"),
                 MODE_CHOICES.get(a.mode, a.mode), a.instead_of or "основа" if a.mode == "instead" else "—"]
                for a in self._adds]
        self.adds.fill(rows)

    def add_additive(self, existing: int | None = None):
        d = AdditiveDialog(self, self._adds[existing] if existing is not None else None,
                           self._components())
        res = d.show()
        if res is None:
            return
        if existing is None:
            self._adds.append(res)
        else:
            self._adds[existing] = res
        self._fill_adds()
        self.recalc()

    def edit_additive(self):
        sel = self.adds.tree.selection()
        if sel:
            self.add_additive(self.adds.tree.index(sel[0]))

    def del_additive(self):
        sel = self.adds.tree.selection()
        if sel:
            del self._adds[self.adds.tree.index(sel[0])]
            self._fill_adds()
            self.recalc()

    def _components(self) -> list[str]:
        try:
            return list(charge.parse_composition(self.e_comp.get(), self.v_basis.get()).values)
        except ChargeError:
            return []

    # ---------------------------------------------------------------- расчёт
    def recipe(self) -> Recipe:
        key = lambda d, v: next(k for k, t in d.items() if t == v)  # noqa: E731
        pure = [p.strip() for p in (self.e_pure.get() or "").replace(";", ",").split(",") if p.strip()]
        lig = self._parse_lig(self.e_ligcomp.get())
        balls = (self.e_balls.get() or "").strip()
        return Recipe(
            alloy=self.e_alloy.get().strip(), composition=self.e_comp.get().strip(), basis=self.v_basis.get(),
            additives=list(self._adds), mode=key(VARIANT_MODES, self.v_mode.get()),
            target_g=_num(self.e_target, name="нужная масса смеси"),
            capacity_g=_num(self.e_cap, name="ёмкость барабана"),
            reserve_pct=_num(self.e_reserve, 0.0, "запас на потери"),
            load_mode=key(LOAD_MODES, self.v_load.get()),
            balls_ratio=(_num(self.e_balls, None, "шары : порошок") if balls else None),
            purity=dict(getattr(self, "_purity", {})),
            ligature_mode=key(LIG_MODES, self.v_lig.get()), pure_components=pure, ligature_comp=lig,
            mass_overrides=dict(self.app.st.atomic_mass_overrides or {}),
            oxygen_warn_wt=float(self.app.st.oxygen_warn_wt))

    @staticmethod
    def _parse_lig(text: str) -> dict:
        """«Ti 81,25; Nb 15,45; Mo 3,26; B 0,04» → {Ti: 81.25, …}."""
        out = {}
        for part in (text or "").replace(";", ",").split(","):
            t = part.split()
            if len(t) == 2:
                try:
                    out[t[0]] = float(t[1].replace(",", "."))
                except ValueError as e:
                    raise ChargeError(f"состав лигатуры: «{part.strip()}» — не число") from e
            elif t:
                raise ChargeError(f"состав лигатуры: «{part.strip()}» — пишите «элемент число», например Ti 81,25")
        return out

    def recalc(self, *_):
        if self._busy:
            return
        try:
            self.result = charge.calculate(self.recipe())
        except ChargeError as e:
            self.result = None
            self.msg.configure(text=str(e), foreground="#FF0000")
            self.app.update_status("Шихта: " + str(e))
            self._clear_tables()
            return
        except Exception as e:  # noqa: BLE001 — любая неожиданность не должна ронять окно
            self.result = None
            self.msg.configure(text=f"Не удалось посчитать: {e}", foreground="#FF0000")
            self._clear_tables()
            return
        self._show(self.result)

    def _clear_tables(self):
        for t in (self.t_var, self.t_load, self.t_lig):
            t.fill([])

    def _chosen(self, res):
        """Вариант, по которому показываются навески (выбор в списке; по умолчанию — последний)."""
        name = self.v_variant.get()
        return next((v for v in res.variants if v.name == name), res.main)

    def _show(self, res):
        names = [v.name for v in res.variants]
        self.cb_variant.configure(values=names)
        if self.v_variant.get() not in names:
            self.v_variant.set(res.main.name)
        chosen = self._chosen(res)
        comps = list(dict.fromkeys(c for v in res.variants for c in v.w))
        cols = [("Вариант", 26, "w")] + [(f"{c}, мас.%", 10, "e") for c in comps] + [("O, мас.%", 9, "e"),
                                                                                    ("ρ, г/см³", 9, "e")]
        self.t_var.set_columns(cols)
        rows = []
        for v in res.variants:
            rows.append([v.name] + [fmt_pct(v.w[c]) if c in v.w else "—" for c in comps]
                        + [fmt_pct(v.oxygen_total) if v.oxygen else "—",
                           f"{v.density.rho:.3f}".replace(".", ",") if v.density else "—"])
        self.t_var.fill(rows)

        loads, buy = res.loads(chosen), res.purchase(chosen)
        self.t_load.fill([[c, fmt_g(g), fmt_g(buy[c]), charge.balance_accuracy(g)] for c, g in loads.items()]
                         + [["Итого", fmt_g(sum(loads.values())), fmt_g(sum(buy.values())), ""]])
        if res.ligature is not None:
            lg = res.ligature
            rows = [["Лигатура", fmt_pct(lg.lig_pct), fmt_g(res.plan.per_load_g * lg.lig_pct / 100)]]
            rows += [[f"{c} (чистый)", fmt_pct(v), fmt_g(res.plan.per_load_g * v / 100)]
                     for c, v in lg.pure.items()]
            rows += [["— состав лигатуры —", "", ""]]
            rows += [[c, fmt_pct(v), ""] for c, v in lg.lig_comp.items()]
            self.t_lig.fill(rows)
        else:
            self.t_lig.fill([])

        lines = charge_report.summary_lines(res, chosen)
        warn = list(res.warnings)
        seen = {}
        for v in res.variants:          # одно и то же замечание у нескольких вариантов — одной строкой
            for _, t in v.flags:
                seen.setdefault(t, []).append(v.name)
        warn += [f"{t} (варианты: {', '.join(names)})" if len(names) > 1 else f"{names[0]}: {t}"
                 for t, names in seen.items()]
        if res.ligature is not None:
            warn += [t for _, t in res.ligature.flags]
        if res.plan.note:
            warn.append(res.plan.note)
        color = theme.TEXT if not warn else "#806000"
        self.msg.configure(text="\n".join(lines + ["⚠ " + w for w in warn]), foreground=color)
        self.app.update_status(f"Шихта: {res.plan.n} загрузок по {fmt_g(res.plan.per_load_g)} г")

    def refresh(self):
        self.recalc()

    # ---------------------------------------------------------------- действия
    def check(self):
        self.recalc()
        if self.result is None:
            messagebox.showerror(APP_NAME, self.msg.cget("text") or "Проверьте ввод.", parent=self)
            return
        warn = [t for v in self.result.variants for _, t in v.flags] + list(self.result.warnings)
        messagebox.showinfo(APP_NAME, "Расчёт выполнен.\n\n" + "\n\n".join(charge_report.summary_lines(self.result)
                                                                           + warn), parent=self)

    def load_example(self, quiet=False):
        self.set_recipe(charge.EXAMPLE)
        if not quiet:
            self.app.log("Шихта: загружен пример из задания коллеги")

    def set_recipe(self, r: Recipe):
        self._busy = True
        try:
            self.e_alloy.delete(0, "end"), self.e_alloy.insert(0, r.alloy)
            self.e_comp.delete(0, "end"), self.e_comp.insert(0, r.composition)
            self.v_basis.set(r.basis)
            self._adds = list(r.additives)
            self._fill_adds()
            self.v_mode.set(VARIANT_MODES.get(r.mode, VARIANT_MODES["both"]))
            for e, v in ((self.e_target, r.target_g), (self.e_cap, r.capacity_g), (self.e_reserve, r.reserve_pct),
                         (self.e_balls, r.balls_ratio)):
                e.delete(0, "end")
                if v is not None:
                    e.insert(0, f"{v:g}".replace(".", ","))
            self.v_load.set(LOAD_MODES.get(r.load_mode, LOAD_MODES["full"]))
            self.v_lig.set(LIG_MODES.get(r.ligature_mode, LIG_MODES["none"]))
            self.e_pure.delete(0, "end"), self.e_pure.insert(0, ", ".join(r.pure_components))
            self.e_ligcomp.delete(0, "end")
            if r.ligature_comp:
                self.e_ligcomp.insert(0, "; ".join(f"{k} {v:g}".replace(".", ",")
                                                   for k, v in r.ligature_comp.items()))
            self._purity = dict(r.purity or {})
        finally:
            self._busy = False
        self.recalc()

    def _need(self):
        self.recalc()
        if self.result is None:
            messagebox.showerror(APP_NAME, self.msg.cget("text") or "Проверьте ввод.", parent=self)
        return self.result

    def export_blank(self):
        res = self._need()
        if not res:
            return
        p = filedialog.asksaveasfilename(parent=self, title="Бланк навесок", initialdir=self.app.st.last_dir or None,
                                         initialfile="Бланк навесок.docx", defaultextension=".docx",
                                         filetypes=[("Документ Word", "*.docx"), ("HTML (для печати)", "*.html")])
        if not p:
            return
        p = Path(p)
        self.app.st.last_dir = str(p.parent)
        try:
            v = self._chosen(res)
            if p.suffix.lower() == ".html":
                charge_report.write_blank_html(res, p, self.v_perload.get(), v)
            else:
                charge_report.write_blank_docx(res, p, self.v_perload.get(), v)
        except PermissionError:
            messagebox.showerror(APP_NAME, f"Не удалось записать {p.name}: файл открыт в другой программе?",
                                 parent=self)
            return
        self.app.log(f"Шихта: бланк навесок сохранён — {p}")
        if messagebox.askyesno(APP_NAME, "Бланк навесок сохранён. Открыть его?", parent=self):
            from ..main_window import open_file

            open_file(p)

    def export_xlsx(self):
        res = self._need()
        if not res:
            return
        p = filedialog.asksaveasfilename(parent=self, title="Расчёт шихты в Excel",
                                         initialdir=self.app.st.last_dir or None, initialfile="Шихта.xlsx",
                                         defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        try:
            charge_report.write_xlsx(res, Path(p), self.v_perload.get(), self._chosen(res))
        except PermissionError:
            messagebox.showerror(APP_NAME, f"Не удалось записать {Path(p).name}: файл открыт в Excel?", parent=self)
            return
        self.app.st.last_dir = str(Path(p).parent)
        self.app.log(f"Шихта: расчёт сохранён в {p}")

    def save_recipe(self):
        res = self._need()
        if not res:
            return
        p = filedialog.asksaveasfilename(parent=self, title="Сохранить рецепт шихты",
                                         initialdir=self.app.st.last_dir or None,
                                         initialfile=(res.recipe.alloy or "рецепт шихты")[:40] + ".json",
                                         defaultextension=".json", filetypes=[("Рецепт шихты", "*.json")])
        if not p:
            return
        Path(p).write_text(json.dumps(res.recipe.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
        self._recipe_path = Path(p)
        self.app.st.last_dir = str(Path(p).parent)
        self.app.log(f"Шихта: рецепт сохранён — {p}")

    def open_recipe(self, path: Path | None = None):
        p = path or filedialog.askopenfilename(parent=self, title="Открыть рецепт шихты",
                                               initialdir=self.app.st.last_dir or None,
                                               filetypes=[("Рецепт шихты", "*.json"), ("Все файлы", "*.*")])
        if not p:
            return
        try:
            r = Recipe.from_json(json.loads(Path(p).read_text(encoding="utf-8")))
        except (OSError, ValueError, ChargeError) as e:
            messagebox.showerror(APP_NAME, f"Не удалось открыть рецепт: {e}", parent=self)
            return
        self.set_recipe(r)
        self._recipe_path = Path(p)
        self.app.log(f"Шихта: открыт рецепт {p}")

    def save_to_batch(self):
        res = self._need()
        if not res:
            return
        from ...core import db

        batches = db.batches(self.app.db)
        if not batches:
            messagebox.showinfo(APP_NAME, "В базе пока нет партий — откройте файлы измерений или добавьте "
                                          "партию на вкладке «База данных».", parent=self)
            return
        d = BatchPickDialog(self, [b["name"] for b in batches], res.recipe.alloy)
        name = d.show()
        if not name:
            return
        bid = db.get_or_create_batch(self.app.db, name)
        rid = db.charge_save(self.app.db, res.recipe.to_json(), res.recipe.alloy or "рецепт", bid)
        self.app.log(f"Шихта: рецепт №{rid} сохранён в карточку партии «{name}»")
        self.app.update_status("Рецепт шихты сохранён в базу")


# ==================================================================== диалоги
class AdditiveDialog(tk.Toplevel):
    def __init__(self, parent, add: Additive | None, components: list[str]):
        super().__init__(parent)
        self.withdraw()
        self.title("Добавка")
        self.transient(parent)
        self.resizable(False, False)
        self.configure(background=theme.FACE)
        self.result = None
        b = tk.Frame(self, background=theme.FACE, padx=theme.px(12), pady=theme.px(10))
        b.pack(fill="both", expand=True)
        tk.Label(b, text="Компонент:").grid(row=0, column=0, sticky="w")
        self.e_comp = tk.Entry(b, width=14)
        self.e_comp.grid(row=0, column=1, sticky="w", pady=theme.px(2))
        tk.Label(b, text="Количество:").grid(row=1, column=0, sticky="w")
        self.e_amount = tk.Entry(b, width=14)
        self.e_amount.grid(row=1, column=1, sticky="w", pady=theme.px(2))
        tk.Label(b, text="Единицы:").grid(row=2, column=0, sticky="w")
        self.v_unit = tk.StringVar()
        self.cb_unit = ttk.Combobox(b, state="readonly", width=12, font=theme.FONTS["ui"], textvariable=self.v_unit)
        self.cb_unit.grid(row=2, column=1, sticky="w", pady=theme.px(2))
        tk.Label(b, text="Вводится:").grid(row=3, column=0, sticky="w")
        self.v_mode = tk.StringVar(value=MODE_CHOICES["instead"])
        cb = ttk.Combobox(b, state="readonly", width=12, font=theme.FONTS["ui"],
                          values=list(MODE_CHOICES.values()), textvariable=self.v_mode)
        cb.grid(row=3, column=1, sticky="w", pady=theme.px(2))
        tk.Label(b, text="За счёт:").grid(row=4, column=0, sticky="w")
        self.v_instead = tk.StringVar()
        self.cb_instead = ttk.Combobox(b, width=12, font=theme.FONTS["ui"], values=components,
                                       textvariable=self.v_instead)
        self.cb_instead.grid(row=4, column=1, sticky="w", pady=theme.px(2))
        self.hint = tk.Label(b, text="", justify="left", wraplength=theme.px(320), foreground=theme.SHADOW)
        self.hint.grid(row=5, column=0, columnspan=2, sticky="w", pady=(theme.px(6), 0))

        bar = tk.Frame(self, background=theme.FACE, padx=theme.px(12), pady=theme.px(10))
        bar.pack(fill="x")
        ttk.Button(bar, text="Отмена", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="OK", command=self.on_ok, default="active").pack(side="right", padx=(0, theme.px(6)))
        self.e_comp.bind("<KeyRelease>", lambda e: self._sync_units())
        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.destroy())
        if add:
            self.e_comp.insert(0, add.component)
            self.e_amount.insert(0, f"{add.amount:g}".replace(".", ","))
            self._sync_units()
            self.v_unit.set(UNIT_CHOICES.get(add.unit or "", ""))
            self.v_mode.set(MODE_CHOICES.get(add.mode, MODE_CHOICES["instead"]))
            self.v_instead.set(add.instead_of or "")
        else:
            self._sync_units()
            if components:
                self.v_instead.set(components[0])

    def _sync_units(self):
        name = (self.e_comp.get() or "").strip()
        compound = bool(name) and charge.is_compound(name)
        vals = ["мол.%", "мас.%"] if compound else ["ат.%", "мас.%"]
        self.cb_unit.configure(values=vals)
        if self.v_unit.get() not in vals:
            self.v_unit.set("" if compound else "ат.%")   # для соединения единицы выбираются явно
        self.hint.configure(text=("Для соединения выберите единицы явно: мол.% — доля формульных единиц "
                                  "(как ат.% у элемента), мас.% — доля массы. Это разные смеси: "
                                  "1,2 мол.% CeO₂ ≈ 4,8 мас.%." if compound else
                                  "«за счёт» — доля выбранного компонента уменьшается на столько же; "
                                  "«сверх» — остальные уменьшаются пропорционально."))

    def on_ok(self):
        unit = {v: k for k, v in UNIT_CHOICES.items()}.get(self.v_unit.get())
        mode = {v: k for k, v in MODE_CHOICES.items()}.get(self.v_mode.get(), "instead")
        try:
            amount = float((self.e_amount.get() or "").replace(",", "."))
        except ValueError:
            messagebox.showerror("Добавка", "Количество — число, например 0,5", parent=self)
            return
        a = Additive(charge.normalize_name(self.e_comp.get().strip()), amount, unit, mode,
                     (self.v_instead.get() or None) if mode == "instead" else None)
        try:
            charge.check_additive(a, a.instead_of)
        except ChargeError as e:
            messagebox.showerror("Добавка", str(e), parent=self)
            return
        self.result = a
        self.destroy()

    def show(self):
        from ..widgets import center_on

        center_on(self, self.master)
        self.deiconify()
        self.grab_set()
        self.e_comp.focus_set()
        self.wait_window()
        return self.result


class BatchPickDialog(tk.Toplevel):
    def __init__(self, parent, names: list[str], suggested: str = ""):
        super().__init__(parent)
        self.withdraw()
        self.title("Сохранить рецепт в карточку партии")
        self.transient(parent)
        self.resizable(False, False)
        self.configure(background=theme.FACE)
        self.result = None
        b = tk.Frame(self, background=theme.FACE, padx=theme.px(12), pady=theme.px(10))
        b.pack(fill="both", expand=True)
        tk.Label(b, text="Партия:").pack(anchor="w")
        self.v = tk.StringVar(value=suggested if suggested in names else (names[0] if names else ""))
        ttk.Combobox(b, width=36, font=theme.FONTS["ui"], values=names, textvariable=self.v).pack(anchor="w")
        tk.Label(b, text="Можно выбрать из списка или вписать новое название.",
                 foreground=theme.SHADOW).pack(anchor="w", pady=(theme.px(4), 0))
        bar = tk.Frame(self, background=theme.FACE, padx=theme.px(12), pady=theme.px(10))
        bar.pack(fill="x")
        ttk.Button(bar, text="Отмена", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Сохранить", command=self.on_ok, default="active").pack(side="right",
                                                                                     padx=(0, theme.px(6)))
        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def on_ok(self):
        self.result = (self.v.get() or "").strip() or None
        self.destroy()

    def show(self):
        from ..widgets import center_on

        center_on(self, self.master)
        self.deiconify()
        self.grab_set()
        self.wait_window()
        return self.result
