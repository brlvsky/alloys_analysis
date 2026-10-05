"""Вкладка «Методика» (М8): встроенный документ SOP и чек-лист качества выбранного измерения."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

from ...core import qc
from ...core.settings import resource_dir
from .. import theme
from ..widgets import NoteBox, PanelTitle, groupbox, scrolled

SOP_PATH = ("psd_lab", "docs", "SOP_laser_diffraction.md")


def sop_text() -> str:
    for base in (resource_dir(), resource_dir().parent):
        p = base.joinpath(*SOP_PATH)
        if p.exists():
            return p.read_text(encoding="utf-8")
    return "# Методика\n\nФайл методики не найден."


def setup_text_tags(t: tk.Text) -> None:
    """Стили для render_markdown: заголовки, жирный, списки, моноширинный код, строки таблиц."""
    fam = theme.FONTS["ui"][0]
    t.tag_configure("h1", font=(fam, 13, "bold"), spacing3=theme.px(6))
    t.tag_configure("h2", font=(fam, 10, "bold"), foreground=theme.SELECT_BG, spacing1=theme.px(4))
    t.tag_configure("h3", font=theme.FONTS["bold"], spacing1=theme.px(3))
    t.tag_configure("b", font=theme.FONTS["bold"])
    t.tag_configure("li", lmargin1=theme.px(12), lmargin2=theme.px(28))
    t.tag_configure("code", font=theme.FONTS["mono"], background="#F0F0F0")
    t.tag_configure("pre", font=theme.FONTS["mono"], background="#F0F0F0", lmargin1=theme.px(12),
                    lmargin2=theme.px(12))
    t.tag_configure("row", lmargin1=theme.px(12), lmargin2=theme.px(28))
    t.tag_configure("hr", foreground=theme.SHADOW, justify="center")


def _inline(t: tk.Text, line: str, tag=()):
    """**жирный** и `код` внутри строки."""
    for i, part in enumerate(re.split(r"\*\*", line)):
        bold = ("b",) if i % 2 else ()
        for j, piece in enumerate(part.split("`")):
            t.insert("end", piece, tag + bold + (("code",) if j % 2 else ()))


def render_markdown(text_widget: tk.Text, md: str) -> list[tuple[int, str, str]]:
    """Простой показ Markdown: заголовки, списки, **жирный**, `код`, блоки кода, таблицы (строка — пункт:
    первая ячейка жирным). Возвращает [(уровень, текст заголовка, метка в тексте)] для оглавления."""
    t = text_widget
    t.configure(state="normal")
    t.delete("1.0", "end")
    heads = []
    pre = False
    in_table = False     # первая строка таблицы — заголовок, его не показываем
    for line in md.splitlines():
        if line.strip().startswith("```"):
            pre = not pre
            continue
        if pre:
            t.insert("end", line + "\n", "pre")
            continue
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not in_table:
                in_table = True
                continue
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            first, rest = cells[0], [c for c in cells[1:] if c]
            t.insert("end", "  ▪ ", "row")
            _inline(t, first, ("row",) if "**" in first else ("row", "b"))
            if rest:
                t.insert("end", " — ", "row")
                _inline(t, "; ".join(rest), ("row",))
            t.insert("end", "\n", "row")
            continue
        in_table = False
        m = re.match(r"^(#{1,3}) (.*)$", line)
        if m:
            lvl, title = len(m.group(1)), m.group(2).strip()
            mark = f"h{len(heads)}"
            t.mark_set(mark, "end-1c")
            t.mark_gravity(mark, "left")
            heads.append((lvl, title.replace("**", ""), mark))
            t.insert("end", ("" if lvl == 1 else "\n") + title.replace("**", "") + "\n", f"h{lvl}")
            continue
        if line.strip() == "---":   # разделитель разделов: отступ уже даёт заголовок
            continue
        tag = ()
        m = re.match(r"^(\s*)(-|\d+\.)\s+(.*)$", line)
        if m:
            bullet = "•" if m.group(2) == "-" else m.group(2)
            t.insert("end", f"  {bullet} ", "li")
            line, tag = m.group(3), ("li",)
        _inline(t, line, tag)
        t.insert("end", "\n", tag)
    t.configure(state="disabled")
    return heads


class MethodTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, background=theme.FACE)
        self.app = app
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = tk.Frame(pw, background=theme.FACE)
        pw.add(left, weight=3)
        PanelTitle(left, "Методика измерения (docs/SOP_laser_diffraction.md)").pack(fill="x")
        frame, self.text = scrolled(left, tk.Text, wrap="word", relief="flat", borderwidth=0, padx=theme.px(10),
                                    pady=theme.px(6), background=theme.FIELD, cursor="arrow",
                                    spacing1=theme.px(1), spacing3=theme.px(2))
        frame.pack(fill="both", expand=True)
        setup_text_tags(self.text)
        render_markdown(self.text, sop_text())

        right = tk.Frame(pw, background=theme.FACE)
        pw.add(right, weight=2)
        self.title = PanelTitle(right, "Чек-лист качества")
        self.title.pack(fill="x")
        g = groupbox(right, "Отметьте выполненные пункты")
        g.pack(fill="x", padx=theme.px(2), pady=theme.px(4))
        self.vars = {}
        self.checks = {}
        for key, text, auto in qc.ITEMS:
            v = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(g, text=text, variable=v, anchor="w", justify="left", wraplength=theme.px(380),
                                command=self.on_change, state="disabled" if auto else "normal")
            cb.pack(fill="x", anchor="w", pady=theme.px(1))
            self.vars[key], self.checks[key] = v, cb
        g.bind("<Configure>", lambda e: [c.configure(wraplength=max(150, e.width - theme.px(40)))
                                         for c in self.checks.values()])
        self.score = tk.Label(right, font=theme.FONTS["big"], anchor="w", foreground=theme.SELECT_BG)
        self.score.pack(fill="x", padx=theme.px(6), pady=theme.px(4))
        self.info = tk.Label(right, anchor="w", justify="left", wraplength=theme.px(400))
        self.info.pack(fill="x", padx=theme.px(6))
        NoteBox(right, "отметки хранятся в базе (measurements.qc_checklist) отдельно для каждого измерения; "
                       "для среднего повторов отметка ставится всем его измерениям, а пункт считается выполненным, "
                       "только если он выполнен у всех. Пункт про обскурацию ставится автоматически по данным "
                       "прибора.", title="Как это работает:").pack(fill="x", padx=theme.px(2), pady=theme.px(6))
        self._sash, self._pw = False, pw

    def refresh(self):
        if not self._sash and self.winfo_ismapped():
            self.update_idletasks()
            self._pw.sashpos(0, int(self.winfo_width() * 0.58))
            self._sash = True
        s = self.app.current
        if s is None:
            self.title.configure(text="Чек-лист качества — выберите образец слева")
            for cb in self.checks.values():
                cb.configure(state="disabled")
            self.score.configure(text="")
            self.info.configure(text="")
            return
        cl, found, meas = self.app.qc_for(s)
        for key, _, auto in qc.ITEMS:
            self.vars[key].set(cl[key])
            self.checks[key].configure(state="disabled" if (auto or not found) else "normal")
        self.title.configure(text=f"Чек-лист качества — {s.label}")
        self.score.configure(text=f"QC: {qc.label(cl)}")
        txt = f"Измерения: {', '.join(meas)}."
        if not found:
            txt += "  Измерение ещё не в базе (идёт импорт) — отметки станут доступны через несколько секунд."
        self.info.configure(text=txt)

    def on_change(self):
        s = self.app.current
        if s is None:
            return
        manual = {k: self.vars[k].get() for k, _, auto in qc.ITEMS if not auto}
        self.app.qc_save(s, manual)
        self.refresh()
