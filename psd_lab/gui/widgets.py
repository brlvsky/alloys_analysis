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
                 relief="solid", borderwidth=1, font=theme.FONTS.get("ui"), padx=3, pady=1).pack()

    def _hide(self, _e=None):
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None


class ToolButton(tk.Button):
    """Плоская кнопка тулбара: приподнимается при наведении, вдавливается при нажатии."""

    def __init__(self, parent, image, command, tooltip="", toggle=False):
        super().__init__(parent, image=image, command=command, relief="flat", overrelief="raised",
                         borderwidth=1, background=theme.FACE, activebackground=theme.FACE,
                         highlightthickness=0, padx=3, pady=3, takefocus=0)
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

    def button(self, image, command, tooltip="", toggle=False) -> ToolButton:
        b = ToolButton(self, image, command, tooltip, toggle)
        b.pack(side="left", padx=0, pady=1)
        return b

    def separator(self):
        f = tk.Frame(self, width=2, background=theme.FACE)
        tk.Frame(f, width=1, background=theme.SHADOW).pack(side="left", fill="y")
        tk.Frame(f, width=1, background=theme.LIGHT).pack(side="left", fill="y")
        f.pack(side="left", fill="y", padx=4, pady=3)


class StatusBar(tk.Frame):
    """Строка состояния из вдавленных секций."""

    def __init__(self, parent, widths=(28, 26, 12, 0)):
        super().__init__(parent, background=theme.FACE)
        self.cells = []
        for i, w in enumerate(widths):
            lab = tk.Label(self, text="", anchor="w", relief="sunken", borderwidth=1, padx=4,
                           background=theme.FACE, width=w or None)
            lab.pack(side="left", fill="x", expand=(w == 0), padx=(2 if i == 0 else 0, 2), pady=2)
            self.cells.append(lab)

    def set(self, i: int, text: str):
        self.cells[i].configure(text=text)


class PanelTitle(tk.Label):
    """Тёмно-синяя полоса с белым жирным заголовком."""

    def __init__(self, parent, text=""):
        super().__init__(parent, text=text, anchor="w", background=theme.TITLE_BG, foreground=theme.TITLE_FG,
                         font=theme.FONTS.get("bold"), padx=4, pady=1)


def sunken(parent, **kw) -> tk.Frame:
    """Вдавленная рамка 2 px для полей, таблиц и графиков."""
    return tk.Frame(parent, relief="sunken", borderwidth=2, background=theme.FACE, **kw)


def groupbox(parent, text) -> ttk.LabelFrame:
    return ttk.LabelFrame(parent, text=text, padding=(8, 4, 8, 8))


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
        self.body = tk.Frame(self, background=theme.FACE, padx=10, pady=8)
        self.body.pack(fill="both", expand=True)
        bar = tk.Frame(self, background=theme.FACE, padx=10, pady=8)
        bar.pack(fill="x")
        self.buttons = {}
        for i, name in enumerate(reversed(buttons)):
            b = ttk.Button(bar, text=name, command=(self.on_ok if name == "OK" else self.on_cancel))
            b.pack(side="right", padx=(6, 0))
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
