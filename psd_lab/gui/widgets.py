"""Виджеты в стиле Win95: тулбар-кнопки, тултипы, статус-бар, заголовок панели, рамки."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme


class Tooltip:
    """Жёлтая подсказка с чёрной рамкой, появляется через 500 мс."""

    def __init__(self, widget: tk.Widget, text: str, delay=500):
        self.widget, self.text, self.delay = widget, text, delay
        self._after = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after:
            self.widget.after_cancel(self._after)
            self._after = None

    def _show(self):
        if self._tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 4
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, background=theme.TOOLTIP_BG, foreground=theme.TEXT,
                 relief="solid", borderwidth=1, font=theme.FONTS.get("ui"), padx=theme.px(4),
                 pady=theme.px(2)).pack()

    def _hide(self, _e=None):
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None


class ToolButton(tk.Button):
    """Плоская кнопка тулбара: приподнимается при наведении, вдавливается при нажатии.

    С text — крупная кнопка «иконка над подписью», как в лабораторном софте конца 90-х.
    """

    def __init__(self, parent, image, command, tooltip="", toggle=False, text=""):
        kw = {}
        if text:
            import tkinter.font as tkfont

            f = tkfont.Font(root=parent, font=theme.FONTS.get("ui"))
            w = max(image.width() + theme.px(22), f.measure(text) + theme.px(14))
            kw = dict(text=text, compound="top", width=w, font=theme.FONTS.get("ui"))
        super().__init__(parent, image=image, command=command, relief="flat", overrelief="raised",
                         borderwidth=max(1, theme.px(1)), background=theme.FACE, activebackground=theme.FACE,
                         highlightthickness=0, padx=theme.px(3), pady=theme.px(3), takefocus=0, **kw)
        self.toggle_state = False
        self._toggle = toggle
        if tooltip:
            Tooltip(self, tooltip)

    def set_pressed(self, pressed: bool):
        self.toggle_state = pressed
        self.configure(relief="sunken" if pressed else "flat",
                       overrelief="sunken" if pressed else "raised",
                       background=theme.LIGHT2 if pressed else theme.FACE)


class Toolbar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, background=theme.FACE, relief="raised", borderwidth=1)

    def button(self, image, command, tooltip="", toggle=False, text="") -> ToolButton:
        b = ToolButton(self, image, command, tooltip, toggle, text)
        b.pack(side="left", padx=(theme.px(1), 0), pady=theme.px(2))
        return b

    def separator(self):
        f = tk.Frame(self, width=2, background=theme.FACE)
        tk.Frame(f, width=1, background=theme.SHADOW).pack(side="left", fill="y")
        tk.Frame(f, width=1, background=theme.LIGHT).pack(side="left", fill="y")
        f.pack(side="left", fill="y", padx=theme.px(5), pady=theme.px(4))


class StatusBar(tk.Frame):
    """Строка состояния из вдавленных секций."""

    def __init__(self, parent, widths=(28, 26, 12, 0)):
        super().__init__(parent, background=theme.FACE)
        self.cells = []
        for i, w in enumerate(widths):
            lab = tk.Label(self, text="", anchor="w", relief="sunken", borderwidth=1, padx=theme.px(4),
                           pady=theme.px(1), background=theme.FACE, width=w or None)
            lab.pack(side="left", fill="x", expand=(w == 0), padx=(theme.px(2) if i == 0 else 0, theme.px(2)),
                     pady=theme.px(2))
            self.cells.append(lab)

    def set(self, i: int, text: str):
        self.cells[i].configure(text=text)


class PanelTitle(tk.Label):
    """Тёмно-синяя полоса с белым жирным заголовком."""

    def __init__(self, parent, text=""):
        super().__init__(parent, text=text, anchor="w", background=theme.TITLE_BG, foreground=theme.TITLE_FG,
                         font=theme.FONTS.get("bold"), padx=theme.px(5), pady=theme.px(2))


def sunken(parent, **kw) -> tk.Frame:
    """Вдавленная рамка 2 px для полей, таблиц и графиков."""
    return tk.Frame(parent, relief="sunken", borderwidth=2, background=theme.FACE, **kw)


def groupbox(parent, text) -> ttk.LabelFrame:
    return ttk.LabelFrame(parent, text=text, padding=(theme.px(8), theme.px(4), theme.px(8), theme.px(8)))


def scrolled(parent, widget_cls, **kw):
    """Виджет + вертикальная прокрутка в вдавленной рамке. Возвращает (рамка, виджет)."""
    frame = sunken(parent)
    w = widget_cls(frame, **kw)
    sb = ttk.Scrollbar(frame, orient="vertical", command=w.yview)
    w.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    w.pack(side="left", fill="both", expand=True)
    return frame, w


def center_on(win: tk.Toplevel, parent: tk.Misc):
    win.update_idletasks()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    if pw < 50:
        pw, ph, px, py = win.winfo_screenwidth(), win.winfo_screenheight(), 0, 0
    win.geometry(f"+{max(0, px + (pw - w) // 2)}+{max(0, py + (ph - h) // 3)}")


class Dialog(tk.Toplevel):
    """Модальный диалог с кнопками OK / Отмена внизу справа."""

    def __init__(self, parent, title, buttons=("OK", "Отмена")):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.configure(background=theme.FACE)
        self.result = None
        self.body = tk.Frame(self, background=theme.FACE, padx=theme.px(12), pady=theme.px(10))
        self.body.pack(fill="both", expand=True)
        bar = tk.Frame(self, background=theme.FACE, padx=theme.px(12), pady=theme.px(10))
        bar.pack(fill="x")
        self.buttons = {}
        for i, name in enumerate(reversed(buttons)):
            b = ttk.Button(bar, text=name, command=(self.on_ok if name == "OK" else self.on_cancel))
            b.pack(side="right", padx=(theme.px(6), 0))
            self.buttons[name] = b
        if "OK" in self.buttons:
            self.buttons["OK"].configure(default="active")
        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def show(self, modal=True):
        center_on(self, self.master)
        self.deiconify()
        if modal:
            self.grab_set()
            self.focus_set()
            self.wait_window()
        return self.result

    def on_ok(self):
        self.result = True
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()


class ReadoutBar(tk.Frame):
    """Ряд «окошек» с результатами, как на панели прибора: подпись сверху, число в белом
    вдавленном поле. set_fields(['d10, мкм', …]) → set_values(['5,81', …])."""

    def __init__(self, parent, title="Результаты"):
        super().__init__(parent, background=theme.FACE)
        self.box = groupbox(self, title)
        self.box.pack(fill="x", padx=theme.px(2), pady=(0, theme.px(2)))
        self.fields: list[str] = []
        self.values: list[tk.Label] = []

    def set_fields(self, labels: list[str], wide=()):
        if labels == self.fields:
            return
        for w in self.box.winfo_children():
            w.destroy()
        self.fields, self.values = list(labels), []
        for i, lab in enumerate(labels):
            tk.Label(self.box, text=lab, font=theme.FONTS["readout_label"], anchor="w").grid(
                row=0, column=i, sticky="w", padx=(0, theme.px(6)))
            v = tk.Label(self.box, text="—", font=theme.FONTS["readout"], anchor="e", relief="sunken",
                         borderwidth=2, background=theme.FIELD, width=9 if lab in wide else 6,
                         padx=theme.px(4), pady=theme.px(1))
            v.grid(row=1, column=i, sticky="we", padx=(0, theme.px(6)))
            self.values.append(v)

    def set_values(self, values: list[str], colors: list[str | None] | None = None):
        colors = colors or [None] * len(values)
        for lab, v, c in zip(self.values, values, colors):
            lab.configure(text=v, foreground=c or theme.TEXT)


class NoteBox(tk.Frame):
    """Жёлтая заметка с чёрной рамкой (как подсказка Win95): «Допущения: …», «Справка: …»."""

    def __init__(self, parent, text="", title="Допущения:", bold=False):
        super().__init__(parent, background=theme.TOOLTIP_BG, highlightbackground=theme.DARK,
                         highlightcolor=theme.DARK, highlightthickness=1)
        self.label = tk.Label(self, background=theme.TOOLTIP_BG, justify="left", anchor="w",
                              padx=theme.px(6), pady=theme.px(4), wraplength=theme.px(640),
                              font=theme.FONTS["bold"] if bold else theme.FONTS["ui"])
        self.label.pack(fill="x")
        self.title = title
        self.set(text)
        self.bind("<Configure>", lambda e: self.label.configure(wraplength=max(200, e.width - theme.px(16))))

    def set(self, text: str, title: str | None = None):
        if title is not None:
            self.title = title
        self.label.configure(text=(f"{self.title} {text}" if self.title else text))


class Table(tk.Frame):
    """Таблица на Treeview в вдавленной рамке: columns = [(заголовок, ширина_симв, anchor)]."""

    def __init__(self, parent, columns, height=6, tree_col=None):
        super().__init__(parent, background=theme.FACE)
        import tkinter.font as tkfont

        frame = sunken(self)
        frame.pack(fill="both", expand=True)
        show = "tree headings" if tree_col else "headings"
        self.tree = ttk.Treeview(frame, columns=[f"c{i}" for i in range(len(columns))], show=show,
                                 height=height, selectmode="browse")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        ch = tkfont.Font(root=self, font=theme.FONTS["ui"]).measure("0") + 1
        if tree_col:
            self.tree.heading("#0", text=tree_col[0])
            self.tree.column("#0", width=tree_col[1] * ch, stretch=False)
        for i, (name, w, anchor) in enumerate(columns):
            self.tree.heading(f"c{i}", text=name)
            self.tree.column(f"c{i}", width=w * ch, anchor=anchor, stretch=(i == 0))

    def fill(self, rows, images=None, texts=None):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            kw = {}
            if images:
                kw["image"] = images[i]
            if texts:
                kw["text"] = texts[i]
            self.tree.insert("", "end", values=["" if v is None else v for v in r], **kw)
