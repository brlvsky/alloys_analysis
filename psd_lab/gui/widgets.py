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
    def __init__(self, parent, grip=True):
        super().__init__(parent, background=theme.FACE, relief="raised", borderwidth=1)
        if grip:   # «ручка» панели, как у панелей инструментов Windows 98
            g = tk.Frame(self, background=theme.FACE)
            g.pack(side="left", fill="y", padx=(theme.px(2), theme.px(4)), pady=theme.px(3))
            for _ in range(2):
                tk.Frame(g, width=max(3, theme.px(3)), relief="raised", borderwidth=1, background=theme.FACE).pack(
                    side="left", fill="y", padx=(0, 1))

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
        # индикатор прогресса (виден только во время долгих операций), как в Windows 95
        self.progress = ChunkProgress(self, width=theme.px(150), height=theme.px(14))

    def set(self, i: int, text: str):
        self.cells[i].configure(text=text)

    def show_progress(self, fraction: float | None):
        """None — спрятать; 0…1 — показать заполнение блоками."""
        if fraction is None:
            self.progress.pack_forget()
            return
        if not self.progress.winfo_ismapped():
            self.progress.pack(side="right", padx=theme.px(2), pady=theme.px(2), before=self.cells[-1])
        self.progress.set(fraction)


class PanelTitle(tk.Canvas):
    """Заголовок панели: градиент тёмно-синий → голубой (как заголовок окна Windows 98), белый жирный текст.

    Совместим с Label: configure(text=…), cget("text").
    """

    def __init__(self, parent, text=""):
        import tkinter.font as tkfont

        f = tkfont.Font(root=parent, font=theme.FONTS.get("bold"))
        self._h = f.metrics("linespace") + 2 * theme.px(2)
        super().__init__(parent, height=self._h, width=theme.px(40), highlightthickness=0, borderwidth=0,
                         background=theme.TITLE_BG)
        self._text = text
        self._img = None
        self._width = 0   # не «_w»: это внутреннее имя виджета в tkinter
        self.bind("<Configure>", self._redraw)

    def configure(self, cnf=None, **kw):  # noqa: D102
        if "text" in kw:
            self._text = kw.pop("text")
            self._draw_text()
        if kw or cnf:
            return super().configure(cnf, **kw)
        return None

    config = configure

    def cget(self, key):
        return self._text if key == "text" else super().cget(key)

    def _redraw(self, e=None):
        w = max(2, (e.width if e else self.winfo_width()))
        if w != self._width:
            self._width = w
            self._img = gradient_image(self, w, self._h, theme.TITLE_BG, theme.TITLE_BG2)
            self.delete("bg")
            self.create_image(0, 0, image=self._img, anchor="nw", tags="bg")
            self.tag_lower("bg")
        self._draw_text()

    def _draw_text(self):
        self.delete("txt")
        self.create_text(theme.px(6), self._h // 2, text=self._text, anchor="w", fill=theme.TITLE_FG,
                         font=theme.FONTS.get("bold"), tags="txt")


_GRAD_CACHE: dict = {}


def gradient_image(master, w, h, c1, c2):
    """Горизонтальный градиент (PhotoImage), кэшируется по размеру."""
    key = (w, h, c1, c2)
    if key not in _GRAD_CACHE:
        import numpy as np
        from PIL import Image, ImageTk

        a = np.array([int(c1[i:i + 2], 16) for i in (1, 3, 5)], float)
        b = np.array([int(c2[i:i + 2], 16) for i in (1, 3, 5)], float)
        k = np.linspace(0, 1, w)[:, None]
        row = (a + (b - a) * k).astype("uint8")[None, :, :]
        img = Image.fromarray(np.repeat(row, h, axis=0), "RGB")
        if len(_GRAD_CACHE) > 64:
            _GRAD_CACHE.clear()
        _GRAD_CACHE[key] = ImageTk.PhotoImage(img, master=master)
    return _GRAD_CACHE[key]


class ChunkProgress(tk.Canvas):
    """Индикатор прогресса Windows 95: тёмно-синие блоки во вдавленной рамке."""

    def __init__(self, parent, width=None, height=None):
        super().__init__(parent, width=width or theme.px(160), height=height or theme.px(16), background=theme.FACE,
                         relief="sunken", borderwidth=1, highlightthickness=0)
        self.value = 0.0
        self.bind("<Configure>", lambda e: self.set(self.value))

    def set(self, fraction: float):
        self.value = max(0.0, min(1.0, fraction))
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(self.cget("width")), int(self.cget("height"))
        pad, gap = 2, max(2, theme.px(2))
        bw = max(4, int(h * 0.6))
        n = int((w - 2 * pad + gap) // (bw + gap))
        k = round(n * self.value)
        for i in range(k):
            x0 = pad + i * (bw + gap)
            self.create_rectangle(x0, pad, x0 + bw, h - pad - 1, fill=theme.PROGRESS, outline="")


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
    """Ряд «окошек» с результатами, как на дисплее прибора: подпись сверху, зелёные цифры на чёрном.
    Окошки переносятся на следующую строку, если не помещаются по ширине.
    set_fields(['d10, мкм', …]) → set_values(['5,81', …])."""

    def __init__(self, parent, title="Результаты"):
        super().__init__(parent, background=theme.FACE)
        self.box = groupbox(self, title)
        self.box.pack(fill="x", padx=theme.px(2), pady=(0, theme.px(2)))
        self.fields: list[str] = []
        self.values: list[tk.Label] = []
        self.cells: list[tk.Frame] = []
        self._cols = 0
        self.box.bind("<Configure>", lambda e: self._reflow())

    def set_fields(self, labels: list[str], wide=()):
        if labels == self.fields:
            return
        for w in self.box.winfo_children():
            w.destroy()
        self.fields, self.values, self.cells = list(labels), [], []
        for lab in labels:
            cell = tk.Frame(self.box, background=theme.FACE)
            tk.Label(cell, text=lab, font=theme.FONTS["readout_label"], anchor="w").pack(fill="x")
            v = tk.Label(cell, text="—", font=theme.FONTS["lcd"], anchor="e", relief="sunken",
                         borderwidth=2, background=theme.LCD_BG, foreground=theme.LCD_FG,
                         width=8 if lab in wide else 6, padx=theme.px(4), pady=theme.px(1))
            v.pack(fill="x")
            self.cells.append(cell)
            self.values.append(v)
        self._cols = 0
        self._reflow()

    def _reflow(self):
        if not self.cells:
            return
        self.box.update_idletasks()
        avail = max(1, self.box.winfo_width() - theme.px(16))
        cw = max(c.winfo_reqwidth() for c in self.cells) + theme.px(6)
        cols = max(1, min(len(self.cells), avail // cw)) if avail > 1 else len(self.cells)
        if cols == self._cols:
            return
        self._cols = cols
        for i, c in enumerate(self.cells):
            c.grid(row=i // cols, column=i % cols, sticky="we", padx=(0, theme.px(6)), pady=(0, theme.px(2)))

    def set_values(self, values: list[str], colors: list[str | None] | None = None):
        """colors: None — обычный зелёный «дисплей», любой цвет — предупреждение (красные цифры)."""
        colors = colors or [None] * len(values)
        for lab, v, c in zip(self.values, values, colors):
            lab.configure(text=v, foreground=theme.LCD_WARN if c else theme.LCD_FG)


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
