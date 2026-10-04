"""Главное окно PSD-Lab."""
from __future__ import annotations

import datetime as dt
import sys
import time
import tkinter as tk
import traceback
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import APP_NAME, __version__
from ..core import expand_paths, load
from ..core.metrics import average_repeats, compute
from ..core.model import LEVEL_NAMES, LEVEL_ORDER, Sample
from ..core.plots import common_axes, draw_compare, draw_sample, plot_all, plot_compare, plot_sample, safe_filename
from ..core.report import write_html, write_xlsx
from ..core.settings import Settings, app_base_dir, data_dir, resource_dir
from . import theme
from .dialogs.about import AboutDialog, Splash
from .dialogs.settings_dialog import SettingsDialog
from .tabs.placeholder import PlaceholderTab
from .tabs.plot_panel import PlotPanel
from .tabs.summary import SummaryTab
from .widgets import PanelTitle, StatusBar, Toolbar, scrolled, sunken

FLAG_ICON = {"ERROR": "flag_error", "WARN": "flag_warn", "INFO": "flag_info", None: "blank"}
TABS = ["Распределение", "Сравнение", "Сводка", "Популяции", "Технология", "Поверхность", "Упаковка",
        "Кинетика", "База данных", "Методика"]


@dataclass
class FileGroup:
    path: Path
    raw: list = field(default_factory=list)     # измерения как в файле
    shown: list = field(default_factory=list)   # после усреднения (или те же)


class MainWindow:
    def __init__(self, root: tk.Tk, settings: Settings, save_settings=True):
        self.root = root
        self.st = settings
        self.save_settings = save_settings
        self.groups: list[FileGroup] = []
        self.items: dict[str, Sample] = {}          # iid дерева → образец
        self.file_items: dict[str, FileGroup] = {}  # iid файла → группа
        self.disabled: set = set()                  # ключи выключенных образцов
        self.current: Sample | None = None

        root.title(f"{APP_NAME} — анализ гранулометрии порошков")
        root.geometry("1280x800")
        root.minsize(900, 560)
        self.ic = lambda n: theme.load_icon(root, n)  # noqa: E731

        self._build_menu()
        self._build_toolbar()
        self.status = StatusBar(root)
        self.status.pack(side="bottom", fill="x")
        self._build_log()
        self._build_body()
        self._bind_keys()
        self.update_status("Готово")
        self.log(f"{APP_NAME} {__version__} запущен. Папка данных: {data_dir()}")

    # ================================================================ построение окна
    def _build_menu(self):
        r = self.root
        mb = tk.Menu(r)
        self.v_log = tk.BooleanVar(value=self.st.show_log)
        self.v_avg = tk.BooleanVar(value=self.st.average)
        self.v_shared = tk.BooleanVar(value=not self.st.independent_axes)
        self.v_name = tk.BooleanVar(value=self.st.show_name)
        self.v_logx = tk.BooleanVar(value=self.st.compare_log)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Открыть файлы…", underline=0, accelerator="Ctrl+O", command=self.open_files)
        m.add_command(label="Открыть папку…", underline=9, command=self.open_folder)
        self.m_recent = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Последние файлы", underline=0, menu=self.m_recent)
        m.add_separator()
        ex = tk.Menu(m, tearoff=0)
        ex.add_command(label="PNG текущего графика…", underline=0, command=self.export_png_current)
        ex.add_command(label="PNG всех графиков…", underline=4, command=self.export_png_all)
        ex.add_command(label="Сводка в Excel (summary.xlsx)…", underline=0, command=self.export_xlsx)
        ex.add_command(label="Отчёт HTML (report.html)…", underline=0, command=self.export_html)
        ex.add_separator()
        ex.add_command(label="Всё в папку…", underline=0, command=self.export_all)
        m.add_cascade(label="Экспорт", underline=0, menu=ex)
        m.add_separator()
        m.add_command(label="Закрыть все файлы", underline=0, command=self.close_all)
        m.add_command(label="Выход", underline=0, accelerator="Alt+F4", command=self.quit)
        mb.add_cascade(label="Файл", underline=0, menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Копировать", underline=0, accelerator="Ctrl+C", command=self.copy)
        m.add_command(label="Переименовать образец", underline=0, accelerator="F2", command=self.rename_selected)
        m.add_separator()
        m.add_command(label="Включить все образцы", underline=0, command=lambda: self.set_all_enabled(True))
        m.add_command(label="Выключить все образцы", underline=1, command=lambda: self.set_all_enabled(False))
        mb.add_cascade(label="Правка", underline=0, menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_checkbutton(label="Журнал", underline=0, variable=self.v_log, command=self.toggle_log)
        m.add_separator()
        m.add_checkbutton(label="Усреднять повторы", underline=0, variable=self.v_avg, command=self.on_view_option)
        m.add_checkbutton(label="Одинаковые оси в файле", underline=0, variable=self.v_shared, command=self.on_view_option)
        m.add_checkbutton(label="Название на графике", underline=0, variable=self.v_name, command=self.on_view_option)
        m.add_checkbutton(label="Логарифмическая ось X сравнения", underline=0, variable=self.v_logx,
                          command=self.on_view_option)
        m.add_separator()
        m.add_command(label="Обновить", underline=1, accelerator="F5", command=self.reload)
        mb.add_cascade(label="Вид", underline=0, menu=m)

        m = tk.Menu(mb, tearoff=0)
        for i, name in enumerate(TABS):
            if name in ("База данных", "Методика"):
                continue
            m.add_command(label=name, underline=0, command=lambda i=i: self.nb.select(i))
        mb.add_cascade(label="Анализ", underline=0, menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Открыть базу данных", underline=0, command=lambda: self.nb.select(TABS.index("База данных")))
        m.add_command(label="Экспорт базы в Excel…", underline=0, state="disabled")
        mb.add_cascade(label="База", underline=0, menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Настройки…", underline=0, command=self.open_settings)
        m.add_command(label="Плотность состава…", underline=0, state="disabled")
        mb.add_cascade(label="Сервис", underline=0, menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Методика измерения", underline=0, command=lambda: self.nb.select(TABS.index("Методика")))
        m.add_separator()
        m.add_command(label="О программе…", underline=2, accelerator="F1", command=self.about)
        mb.add_cascade(label="Справка", underline=1, menu=m)

        r.configure(menu=mb)
        self.menubar = mb
        self._fill_recent()

    def _build_toolbar(self):
        tb = Toolbar(self.root)
        tb.pack(side="top", fill="x")
        tb.button(self.ic("open"), self.open_files, "Открыть файлы (Ctrl+O)")
        tb.button(self.ic("open_dir"), self.open_folder, "Открыть папку")
        tb.separator()
        tb.button(self.ic("export_png"), self.export_png_current, "Экспорт PNG текущего графика")
        tb.button(self.ic("report"), self.export_html, "Отчёт HTML")
        tb.button(self.ic("excel"), self.export_xlsx, "Сводка в Excel")
        tb.separator()
        tb.button(self.ic("refresh"), self.reload, "Обновить (F5)")
        tb.button(self.ic("settings"), self.open_settings, "Настройки")
        tb.separator()
        tb.button(self.ic("help"), self.about, "О программе (F1)")
        self.toolbar = tb

    def _build_body(self):
        pw = ttk.PanedWindow(self.root, orient="horizontal")
        pw.pack(side="top", fill="both", expand=True, padx=2, pady=2)

        left = ttk.PanedWindow(pw, orient="vertical")
        top = tk.Frame(left, background=theme.FACE)
        PanelTitle(top, "Файлы и образцы").pack(fill="x")
        tf = sunken(top)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.column("#0", width=260)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Button-1>", self.on_tree_click, add="+")
        self.tree.bind("<space>", lambda e: self.toggle_item(self.tree.focus()))
        self.tree.bind("<F2>", lambda e: self.rename_selected())
        left.add(top, weight=3)

        bottom = tk.Frame(left, background=theme.FACE)
        PanelTitle(bottom, "Свойства").pack(fill="x")
        pf, self.props = scrolled(bottom, tk.Text, height=10, width=36, wrap="word", relief="flat",
                                  borderwidth=0, background=theme.FIELD, padx=4, pady=2, cursor="arrow")
        pf.pack(fill="both", expand=True)
        self.props.tag_configure("key", foreground=theme.SHADOW)
        self.props.tag_configure("head", font=theme.FONTS["bold"])
        for lv, (bg, fg) in theme.FLAG_COLORS.items():
            self.props.tag_configure(lv, background=bg, foreground=fg, font=theme.FONTS["bold"])
        self.props.configure(state="disabled")
        left.add(bottom, weight=2)
        pw.add(left, weight=0)

        right = tk.Frame(pw, background=theme.FACE)
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)
        self.dist = PlotPanel(self.nb, "Распределение", on_save=self.export_png_current)
        self.cmp = PlotPanel(self.nb, "Сравнение накопленных кривых", on_save=self.export_png_current,
                             extra=self._compare_toolbar)
        self.summary = SummaryTab(self.nb, on_select=self.on_summary_select)
        tabs = {"Распределение": self.dist, "Сравнение": self.cmp, "Сводка": self.summary}
        for name in TABS:
            w = tabs.get(name) or PlaceholderTab(self.nb, name)
            self.nb.add(w, text=name, underline=0 if name in tabs else -1)
        self.nb.enable_traversal()
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.refresh_tab())
        pw.add(right, weight=1)
        self._empty_plots()

    def _compare_toolbar(self, tb):
        tk.Checkbutton(tb, text="Лог. ось X", variable=self.v_logx, command=self.on_view_option,
                       background=theme.FACE, activebackground=theme.FACE).pack(side="left", padx=4)

    def _build_log(self):
        self.log_frame = tk.Frame(self.root, background=theme.FACE)
        self.log_frame.pack(side="bottom", fill="x")
        head = tk.Frame(self.log_frame, background=theme.FACE)
        head.pack(fill="x")
        tk.Label(head, text="Журнал", font=theme.FONTS["bold"]).pack(side="left", padx=4)
        self.log_btn = ttk.Button(head, text="Скрыть", width=-8, command=lambda: self._set_log(not self.v_log.get()))
        self.log_btn.pack(side="right", padx=2, pady=1)
        self.log_body, self.log_text = None, None
        frame = sunken(self.log_frame)
        self.log_text = tk.Text(frame, height=5, font=theme.FONTS["mono"], relief="flat", borderwidth=0,
                                background=theme.FIELD, wrap="none")
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=ys.set, state="disabled")
        ys.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)
        self.log_body = frame
        self._set_log(self.v_log.get())

    def _bind_keys(self):
        r = self.root
        r.bind_all("<Control-o>", lambda e: self.open_files())
        r.bind_all("<Control-O>", lambda e: self.open_files())
        r.bind_all("<F5>", lambda e: self.reload())
        r.bind_all("<F1>", lambda e: self.about())
        r.protocol("WM_DELETE_WINDOW", self.quit)

    # ================================================================ журнал и статус
    def log(self, msg: str):
        t = self.log_text
        t.configure(state="normal")
        t.insert("end", f"{dt.datetime.now():%H:%M:%S}  {msg}\n")
        t.see("end")
        t.configure(state="disabled")

    def _set_log(self, show: bool):
        self.v_log.set(show)
        self.st.show_log = show
        if show:
            self.log_body.pack(fill="x", padx=2, pady=(0, 2))
            self.log_btn.configure(text="Скрыть")
        else:
            self.log_body.pack_forget()
            self.log_btn.configure(text="Показать")

    def toggle_log(self):
        self._set_log(self.v_log.get())

    def update_status(self, text=None):
        if text is not None:
            self.status.set(0, text)
        allv = self.all_samples()
        en = self.enabled_samples()
        self.status.set(1, f"Образцов: {len(allv)} (выбрано {len(en)})")
        nflag = sum(1 for s in en if any(f[0] in ("ERROR", "WARN") for f in s.flags))
        self.status.set(2, f"Флаги: {nflag}")
        self.status.set(3, f"Данные: {data_dir()}")

    # ================================================================ данные
    def all_samples(self) -> list[Sample]:
        return [s for g in self.groups for s in g.shown]

    @staticmethod
    def key(s: Sample):
        return (s.file, s.name, s.meas_id)

    def enabled_samples(self) -> list[Sample]:
        return [s for s in self.all_samples() if self.key(s) not in self.disabled]

    def enabled_groups(self) -> list[list[Sample]]:
        out = []
        for g in self.groups:
            en = [s for s in g.shown if self.key(s) not in self.disabled]
            if en:
                out.append(en)
        return out

    def load_paths(self, paths):
        files = expand_paths(paths)
        if not files:
            self.log("Файлы не найдены: " + ", ".join(str(p) for p in paths))
            return
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        loaded = 0
        try:
            for f in files:
                f = Path(f).resolve()
                if any(g.path == f for g in self.groups):
                    self.log(f"ПРОПУЩЕН  {f.name}: уже открыт (F5 — перечитать)")
                    continue
                try:
                    raw = load(f)
                except Exception as e:  # noqa: BLE001
                    self.log(f"ПРОПУЩЕН  {f.name}: не удалось прочитать ({e})")
                    continue
                if not raw:
                    self.log(f"ПРОПУЩЕН  {f.name}: не найдено распределений")
                    continue
                kind = "экспорт Fritsch" if raw[0].source == "fritsch" else "таблица"
                self.log(f"ЗАГРУЖЕН  {f.name}: {len(raw)} изм. ({kind})")
                self.groups.append(FileGroup(f, raw))
                self.st.add_recent(f)
                loaded += 1
        finally:
            self.root.configure(cursor="")
        self._fill_recent()
        self.rebuild()
        if loaded and self.current is None:
            self.select_first()
        self.update_status(f"Загружено файлов: {loaded}")

    def rebuild(self):
        """Пересчитать усреднение и перестроить дерево и вкладки."""
        for g in self.groups:
            g.shown = average_repeats(g.raw) if self.st.average else list(g.raw)
        cur_key = self.key(self.current) if self.current else None
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self.file_items.clear()
        self.current = None
        for gi, g in enumerate(self.groups):
            fid = f"f{gi}"
            self.tree.insert("", "end", iid=fid, text=" " + g.path.name, open=True)
            self.file_items[fid] = g
            for si, s in enumerate(g.shown):
                sid = f"f{gi}s{si}"
                self.tree.insert(fid, "end", iid=sid, text=" " + s.label)
                self.items[sid] = s
                if cur_key == self.key(s):
                    self.current = s
                    self.tree.selection_set(sid)
                    self.tree.see(sid)
        self.refresh_icons()
        self.refresh_all()

    def refresh_icons(self):
        for fid, g in self.file_items.items():
            on = any(self.key(s) not in self.disabled for s in g.shown)
            self.tree.item(fid, image=theme.composite_icon(self.root, ["check_on" if on else "check_off", "sample"]))
        for sid, s in self.items.items():
            on = self.key(s) not in self.disabled
            self.tree.item(sid, image=theme.composite_icon(
                self.root, ["check_on" if on else "check_off", FLAG_ICON[s.worst_level]]))

    def select_first(self):
        if self.items:
            sid = next(iter(self.items))
            self.tree.selection_set(sid)
            self.tree.focus(sid)
            self.tree.see(sid)
            self.current = self.items[sid]
            self.refresh_all()

    def reload(self):
        paths = [g.path for g in self.groups]
        self.groups.clear()
        self.log("Перечитываю файлы…")
        if paths:
            self.load_paths(paths)
        else:
            self.rebuild()
            self.update_status("Готово")

    def close_all(self):
        self.groups.clear()
        self.disabled.clear()
        self.current = None
        self.rebuild()
        self.update_status("Файлы закрыты")

    # ================================================================ дерево
    def on_tree_click(self, e):
        iid = self.tree.identify_row(e.y)
        if iid and "image" in self.tree.identify_element(e.x, e.y):
            self.toggle_item(iid)
            return "break"
        return None

    def toggle_item(self, iid):
        if iid in self.items:
            k = self.key(self.items[iid])
            self.disabled.symmetric_difference_update({k})
        elif iid in self.file_items:
            ks = {self.key(s) for s in self.file_items[iid].shown}
            if ks <= self.disabled:
                self.disabled -= ks
            else:
                self.disabled |= ks
        else:
            return
        self.refresh_icons()
        self.refresh_all(keep_dist=True)

    def set_all_enabled(self, on: bool):
        self.disabled = set() if on else {self.key(s) for s in self.all_samples()}
        self.refresh_icons()
        self.refresh_all(keep_dist=True)

    def on_tree_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid in self.file_items:
            g = self.file_items[iid]
            self.current = g.shown[0] if g.shown else None
            self.show_props(None, g)
        else:
            self.current = self.items.get(iid)
            self.show_props(self.current)
        self.refresh_dist()

    def on_summary_select(self, samples):
        if samples:
            s = samples[0]
            for sid, x in self.items.items():
                if x is s:
                    self.tree.selection_set(sid)
                    self.tree.see(sid)
                    break

    def rename_selected(self):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.items:
            return
        iid = sel[0]
        s = self.items[iid]
        self.tree.see(iid)
        self.root.update_idletasks()
        bbox = self.tree.bbox(iid, "#0")
        if not bbox:
            return
        x, y, w, h = bbox
        off = theme.icon_size(self.root) * 2 + 6
        ent = tk.Entry(self.tree, relief="solid", borderwidth=1)
        ent.insert(0, s.name)
        ent.select_range(0, "end")
        ent.place(x=x + off, y=y, width=max(120, w - off), height=h)
        ent.focus_set()

        def done(save):
            new = ent.get().strip()
            ent.destroy()
            if save and new and new != s.name:
                self.apply_rename(s, new)

        ent.bind("<Return>", lambda e: done(True))
        ent.bind("<KP_Enter>", lambda e: done(True))
        ent.bind("<Escape>", lambda e: done(False))
        ent.bind("<FocusOut>", lambda e: done(True))

    def apply_rename(self, s: Sample, new: str):
        """Имя меняется у всех исходных измерений образца (чтобы усреднение не сломалось)."""
        old = s.name
        for g in self.groups:
            if g.path != Path(s.file).resolve() and str(g.path) != s.file:
                continue
            for r in g.raw:
                if r.name == old and (not s.members or r.meas_id in s.members) and \
                        (s.members or r.meas_id == s.meas_id):
                    r.name = new
        was_disabled = self.key(s) in self.disabled
        self.log(f"Переименован: «{old}» → «{new}»")
        cur = self.current is s
        self.rebuild()
        for sid, x in self.items.items():
            if x.name == new and x.file == s.file:
                if was_disabled:
                    self.disabled.add(self.key(x))
                if cur:
                    self.tree.selection_set(sid)
                break
        self.refresh_icons()

    # ================================================================ свойства
    def show_props(self, s: Sample | None, group: FileGroup | None = None):
        t = self.props
        t.configure(state="normal")
        t.delete("1.0", "end")
        if group is not None:
            t.insert("end", group.path.name + "\n", "head")
            t.insert("end", "Папка: ", "key")
            t.insert("end", f"{group.path.parent}\n")
            t.insert("end", "Измерений: ", "key")
            t.insert("end", f"{len(group.raw)}; образцов: {len(group.shown)}\n")
        elif s is not None:
            t.insert("end", s.label + "\n", "head")
            m = s.meta
            rows = [("Файл", Path(s.file).name), ("Лист", s.sheet),
                    ("Источник", "экспорт Fritsch" if s.source == "fritsch" else "таблица")]
            if s.members:
                rows.append(("Повторы", f"{len(s.members)}, расхождение до {m.get('repeat_spread_pp', 0):.2f} п.п."))
            if m.get("date"):
                rows.append(("Дата", f"{m['date']:%d.%m.%Y %H:%M}" if hasattr(m["date"], "strftime") else str(m["date"])))
            for k, name, fmt in (("model", "Модель", "{}"), ("obscuration", "Обскурация, %", "{:g}"),
                                 ("error", "Error", "{:.4f}"), ("tradeoff", "TradeOff", "{:.0f}"),
                                 ("ultrasonics", "Ультразвук", "{:g}"), ("pump", "Насос", "{:g}"),
                                 ("d43_instrument", "D[4,3] прибора, мкм", "{:.2f}")):
                v = m.get(k)
                if v is not None:
                    rows.append((name, fmt.format(v)))
            mm = compute(s, self.st.windows_tuples)
            rows.append(("d10 / d50 / d90", f"{mm['d10']:.2f} / {mm['d50']:.2f} / {mm['d90']:.2f} мкм"))
            for k, v in rows:
                t.insert("end", f"{k}: ", "key")
                t.insert("end", f"{v}\n")
            t.insert("end", "\nФлаги качества:\n", "head")
            if not s.flags:
                t.insert("end", "нет\n")
            for f in sorted(s.flags, key=lambda f: LEVEL_ORDER.get(f[0], 9)):
                t.insert("end", f" {LEVEL_NAMES.get(f[0], f[0])} ", f[0])
                t.insert("end", f" {f[1]}\n")
        t.configure(state="disabled")

    # ================================================================ вкладки
    def _empty_plots(self):
        for p, text in ((self.dist, "Откройте файлы: Файл → Открыть файлы… (Ctrl+O)"),
                        (self.cmp, "Нет выбранных образцов")):
            p.figure.clear()
            ax = p.figure.add_subplot(111)
            ax.axis("off")
            ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=11, color="#808080")
            p.draw()

    def refresh_all(self, keep_dist=False):
        if not keep_dist or self.current is None:
            self.refresh_dist()
        self.refresh_cmp()
        self.summary.show(self.enabled_samples(), self.st.windows_tuples)
        if self.current is not None:
            self.show_props(self.current)
        self.update_status()

    def refresh_tab(self):
        pass  # всё обновляется сразу; хук для будущих вкладок

    def refresh_dist(self):
        s = self.current
        if s is None:
            self._empty_plots()
            self.dist.set_title("Распределение")
            return
        grp = next((g.shown for g in self.groups if s in g.shown), [s])
        xm, ym = (None, None) if self.st.independent_axes else common_axes(grp, self.st.bin_um, self.st.xmax)
        draw_sample(self.dist.figure, s, lang=self.st.lang, bin_um=self.st.bin_um, xmax=self.st.xmax or xm,
                    ymax=ym, show_name=self.st.show_name, font_scale=0.85)
        self.dist.set_title(f"Распределение — {s.label}")
        self.dist.draw()

    def refresh_cmp(self):
        groups = self.enabled_groups()
        if not groups:
            self._empty_plots() if self.current is None else None
            self.cmp.figure.clear()
            ax = self.cmp.figure.add_subplot(111)
            ax.axis("off")
            ax.text(0.5, 0.5, "Нет выбранных образцов", ha="center", va="center", fontsize=11, color="#808080")
            self.cmp.draw()
            return
        draw_compare(self.cmp.figure, groups, lang=self.st.lang, log_x=self.st.compare_log,
                     xmax=self.st.xmax, font_scale=0.85)
        n = sum(len(g) for g in groups)
        self.cmp.set_title(f"Сравнение накопленных кривых — образцов: {n}")
        self.cmp.draw()

    def on_view_option(self):
        avg_changed = self.st.average != self.v_avg.get()
        self.st.average = self.v_avg.get()
        self.st.independent_axes = not self.v_shared.get()
        self.st.show_name = self.v_name.get()
        self.st.compare_log = self.v_logx.get()
        if avg_changed:
            self.rebuild()
        else:
            self.refresh_all()

    # ================================================================ экспорт
    def _ask_dir(self, title):
        d = filedialog.askdirectory(parent=self.root, title=title, initialdir=self.st.last_dir or None)
        if d:
            self.st.last_dir = d
        return Path(d) if d else None

    def _ask_save(self, title, name, ext, types):
        p = filedialog.asksaveasfilename(parent=self.root, title=title, initialfile=name, defaultextension=ext,
                                         filetypes=types, initialdir=self.st.last_dir or None)
        if p:
            self.st.last_dir = str(Path(p).parent)
        return Path(p) if p else None

    def _need_data(self) -> bool:
        if not self.enabled_samples():
            messagebox.showinfo(APP_NAME, "Нет выбранных образцов. Откройте файлы и отметьте образцы флажками.",
                                parent=self.root)
            return False
        return True

    def export_png_current(self):
        on_cmp = self.nb.index("current") == TABS.index("Сравнение")
        if on_cmp:
            if not self._need_data():
                return
            p = self._ask_save("Сохранить сравнение", "compare.png", ".png", [("PNG", "*.png")])
            if p:
                plot_compare(self.enabled_groups(), p, lang=self.st.lang, log_x=self.st.compare_log, xmax=self.st.xmax)
                self.log(f"Сохранён {p}")
            return
        s = self.current
        if s is None:
            self._need_data()
            return
        p = self._ask_save("Сохранить график", safe_filename(s.name) + ".png", ".png", [("PNG", "*.png")])
        if p:
            grp = next((g.shown for g in self.groups if s in g.shown), [s])
            xm, ym = (None, None) if self.st.independent_axes else common_axes(grp, self.st.bin_um, self.st.xmax)
            plot_sample(s, p, lang=self.st.lang, bin_um=self.st.bin_um, xmax=self.st.xmax or xm, ymax=ym,
                        show_name=self.st.show_name)
            self.log(f"Сохранён {p}")

    def export_png_all(self, out: Path | None = None):
        if not self._need_data():
            return
        out = out or self._ask_dir("Папка для PNG")
        if not out:
            return
        made = plot_all([(g[0].file, g) for g in self.enabled_groups()], out, lang=self.st.lang,
                        bin_um=self.st.bin_um, xmax=self.st.xmax, independent_axes=self.st.independent_axes,
                        show_name=self.st.show_name, log_x=self.st.compare_log)
        self.log(f"Сохранено PNG: {len(made)} в {out}")
        self.update_status(f"Сохранено PNG: {len(made)}")

    def export_xlsx(self, path: Path | None = None):
        if not self._need_data():
            return
        path = path or self._ask_save("Сводка в Excel", "summary.xlsx", ".xlsx", [("Excel", "*.xlsx")])
        if path:
            try:
                write_xlsx(self.enabled_samples(), path, self.st.windows_tuples)
            except PermissionError:
                messagebox.showerror(APP_NAME, f"Не удалось записать {path.name}.\nВозможно, файл открыт в Excel — "
                                     "закройте его и повторите.", parent=self.root)
                return
            self.log(f"Сохранена сводка {path}")
            self.update_status("Сводка сохранена")

    def export_html(self, path: Path | None = None, ask_open=True):
        if not self._need_data():
            return
        path = path or self._ask_save("Отчёт HTML", "report.html", ".html", [("HTML", "*.html")])
        if not path:
            return
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        try:
            write_html(self.enabled_samples(), path, windows=self.st.windows_tuples, lang=self.st.lang,
                       bin_um=self.st.bin_um, xmax=self.st.xmax, independent_axes=self.st.independent_axes,
                       show_name=self.st.show_name, log_x=self.st.compare_log,
                       files=[g.path for g in self.groups])
        finally:
            self.root.configure(cursor="")
        self.log(f"Сохранён отчёт {path}")
        self.update_status("Отчёт сохранён")
        if ask_open and messagebox.askyesno(APP_NAME, "Отчёт сохранён. Открыть его в браузере?", parent=self.root):
            webbrowser.open(path.resolve().as_uri())

    def export_all(self):
        if not self._need_data():
            return
        out = self._ask_dir("Папка для отчёта, таблицы и графиков")
        if not out:
            return
        self.export_png_all(out)
        self.export_xlsx(out / "summary.xlsx")
        self.export_html(out / "report.html")

    # ================================================================ прочее
    def copy(self):
        if self.nb.index("current") == TABS.index("Сводка"):
            self.summary.copy()
        elif self.nb.index("current") == TABS.index("Сравнение"):
            self.cmp.copy()
        else:
            self.dist.copy()

    def open_files(self):
        paths = filedialog.askopenfilenames(
            parent=self.root, title="Открыть файлы анализатора",
            initialdir=self.st.last_dir or None,
            filetypes=[("Данные гранулометрии", "*.xls *.xlsx *.xlsm *.csv *.txt *.tsv *.dat"),
                       ("Excel", "*.xls *.xlsx"), ("Текст", "*.csv *.txt"), ("Все файлы", "*.*")])
        if paths:
            self.st.last_dir = str(Path(paths[0]).parent)
            self.load_paths(paths)

    def open_folder(self):
        d = self._ask_dir("Открыть папку с файлами")
        if d:
            self.load_paths([d])

    def _fill_recent(self):
        m = self.m_recent
        m.delete(0, "end")
        if not self.st.recent_files:
            m.add_command(label="(пусто)", state="disabled")
            return
        for i, p in enumerate(self.st.recent_files, 1):
            m.add_command(label=f"{i} {p}", underline=0, command=lambda p=p: self.load_paths([p]))

    def open_settings(self):
        old_avg = self.st.average
        if SettingsDialog(self.root, self.st).show():
            self.v_avg.set(self.st.average)
            self.v_shared.set(not self.st.independent_axes)
            self.v_name.set(self.st.show_name)
            self._save_settings()
            self.log("Настройки сохранены")
            if old_avg != self.st.average:
                self.rebuild()
            else:
                self.refresh_all()

    def about(self):
        AboutDialog(self.root).show()

    def _save_settings(self):
        if self.save_settings:
            try:
                self.st.save()
            except OSError as e:
                self.log(f"Не удалось сохранить настройки: {e}")

    def quit(self):
        self._save_settings()
        self.root.destroy()


# ==================================================================== скриншоты и запуск
def window_bbox(win: tk.Misc):
    """Координаты окна на экране вместе с рамкой и меню."""
    win.update_idletasks()
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(win.wm_frame(), 16)
            rect = wintypes.RECT()
            if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            return rect.left, rect.top, rect.right, rect.bottom
        except Exception:  # noqa: BLE001
            pass
    x, y = win.winfo_rootx(), win.winfo_rooty()
    top = y
    if isinstance(win, (tk.Tk, tk.Toplevel)) and win.cget("menu"):
        # X11: строка меню над клиентской областью; wm geometry даёт верх окна вместе с ней
        gy = int(win.wm_geometry().split("+")[2])
        top = min(y, gy)
    return x, top, x + win.winfo_width(), y + win.winfo_height()


def grab(win: tk.Misc, path: Path) -> Path:
    from PIL import ImageGrab

    win.update()
    time.sleep(0.15)
    win.update()
    kw = {"all_screens": True} if sys.platform == "win32" else {}
    img = ImageGrab.grab(bbox=window_bbox(win), **kw)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def run_selftest(win: MainWindow, out: Path, splash_shot: Path | None) -> int:
    root = win.root
    shots = [splash_shot] if splash_shot else []
    raw = next((p for p in (Path.cwd() / "data" / "raw", app_base_dir() / "data" / "raw",
                            resource_dir() / "data" / "raw") if p.is_dir()), None)
    if raw is None:
        print("SELFTEST: папка data/raw не найдена", file=sys.stderr)
        return 1
    win.load_paths([raw])
    n = len(win.all_samples())
    print(f"SELFTEST: загружено образцов: {n}")
    # выбрать бимодальный образец, если он есть — на нём лучше видно графики
    for sid, s in win.items.items():
        if s.name == "П/С +0,5Y2O3":
            win.tree.selection_set(sid)
            win.tree.see(sid)
            break
    root.update()
    for i, name in enumerate(TABS):
        win.nb.select(i)
        shots.append(grab(root, out / f"{i + 1:02d}_{safe_filename(name)}.png"))
    win.nb.select(0)
    for name, cls in (("settings", lambda: SettingsDialog(root, win.st)), ("about", lambda: AboutDialog(root))):
        d = cls()
        from .widgets import center_on

        center_on(d, root)
        d.deiconify()
        shots.append(grab(d, out / f"dlg_{name}.png"))
        d.destroy()
    for p in shots:
        print(f"SELFTEST: скриншот {p}")
    ok = n > 0
    print("SELFTEST: OK" if ok else "SELFTEST: ОШИБКА — нет образцов")
    return 0 if ok else 1


def run_gui(files=None, selftest=False, out=None) -> int:
    theme.setup_dpi()
    root = tk.Tk()
    root.withdraw()
    theme.apply(root)
    try:
        root.iconphoto(True, theme.load_icon(root, "app", 32), theme.load_icon(root, "app", 16))
        if sys.platform == "win32":
            root.iconbitmap(default=str(resource_dir() / "assets" / "app.ico"))
    except tk.TclError:
        pass
    settings = Settings() if selftest else Settings.load()
    code = {"rc": 0}
    out_dir = Path(out or "out") / "screens"

    splash = Splash(root) if (settings.splash or selftest) else None
    if splash:
        root.update()
    win = MainWindow(root, settings, save_settings=not selftest)

    def start():
        shot = None
        if splash:
            if selftest:
                shot = grab(splash, out_dir / "00_splash.png")
            splash.destroy()
        root.deiconify()
        root.update()
        if files:
            win.load_paths(files)
        if selftest:
            try:
                code["rc"] = run_selftest(win, out_dir, shot)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                code["rc"] = 1
            root.destroy()

    root.after(1000 if splash else 0, start)
    root.mainloop()
    return code["rc"]
