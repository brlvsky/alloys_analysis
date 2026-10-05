"""Панель графика: заголовок, свой тулбар Win95 (Масштаб, Сдвиг, Сброс, Копировать, Сохранить PNG)
и холст matplotlib в вдавленной рамке."""
from __future__ import annotations

import io
import sys
import tkinter as tk
import warnings
from tkinter import messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .. import theme
from ..widgets import PanelTitle, Toolbar, sunken

# при очень маленьком окне matplotlib не может уместить подписи — это не ошибка
warnings.filterwarnings("ignore", message="Tight layout not applied")


def copy_png_to_clipboard(fig: Figure) -> bool:
    """Копирует картинку фигуры в буфер обмена Windows (CF_DIB). Вне Windows — False."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    from PIL import Image

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=fig.dpi, facecolor="white")
    buf.seek(0)
    bmp = io.BytesIO()
    Image.open(buf).convert("RGB").save(bmp, "BMP")
    data = bmp.getvalue()[14:]  # без BITMAPFILEHEADER → DIB

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    CF_DIB, GMEM_MOVEABLE = 8, 0x0002
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_DIB, h)
    finally:
        user32.CloseClipboard()
    return True


class PlotPanel(tk.Frame):
    """on_save — функция без аргументов, сохраняющая PNG в публикационном стиле."""

    def __init__(self, parent, title="", on_save=None, extra=None):
        super().__init__(parent, background=theme.FACE)
        self.title = PanelTitle(self, title)
        self.title.pack(fill="x")
        self.toolbar = Toolbar(self)
        self.toolbar.pack(fill="x")
        ic = lambda n: theme.load_icon(self, n, 2 * theme.icon_px())  # noqa: E731
        self.b_zoom = self.toolbar.button(ic("zoom"), self.zoom, "Масштаб: выделите область мышью", toggle=True)
        self.b_pan = self.toolbar.button(ic("pan"), self.pan, "Сдвиг: тащите график мышью", toggle=True)
        self.toolbar.button(ic("home"), self.home, "Сброс масштаба")
        self.toolbar.separator()
        self.toolbar.button(ic("copy"), self.copy, "Копировать в буфер обмена")
        self.toolbar.button(ic("save"), on_save or (lambda: None), "Сохранить PNG (публикационный стиль)")
        if extra:
            self.toolbar.separator()
            extra(self.toolbar)

        frame = sunken(self)
        frame.pack(fill="both", expand=True, padx=theme.px(2), pady=theme.px(2))
        self.plot_frame = frame
        # маленький исходный размер: холст не «распирает» окно, а растягивается вместе с ним
        self.figure = Figure(figsize=(4, 3), dpi=theme.fig_dpi(), layout="tight")
        self.figure.patch.set_facecolor("white")
        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().configure(background="white", highlightthickness=0, borderwidth=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        # стандартный тулбар matplotlib не показываем — используем его действия
        self._nav = NavigationToolbar2Tk(self.canvas, frame, pack_toolbar=False)

    def set_title(self, text: str):
        self.title.configure(text=text)

    def draw(self):
        self._nav.update()  # сбрасывает историю масштаба под новый график
        # подогнать фигуру под фактический размер холста (после смены масштаба экрана
        # matplotlib может не успеть получить событие изменения размера)
        w = self.canvas.get_tk_widget()
        w.update_idletasks()
        cw, ch = w.winfo_width(), w.winfo_height()
        if cw > 20 and ch > 20:
            self.figure.set_size_inches(cw / self.figure.dpi, ch / self.figure.dpi, forward=False)
        # tight_layout() в функциях рисования выключает движок компоновки — включаем обратно,
        # чтобы график перекомпоновывался при каждом изменении размера окна
        self.figure.set_layout_engine("tight")
        self.canvas.draw_idle()

    def zoom(self):
        self._nav.zoom()
        self.b_zoom.set_pressed(self._nav.mode.name == "ZOOM")
        self.b_pan.set_pressed(False)

    def pan(self):
        self._nav.pan()
        self.b_pan.set_pressed(self._nav.mode.name == "PAN")
        self.b_zoom.set_pressed(False)

    def home(self):
        self._nav.home()

    def copy(self):
        if not copy_png_to_clipboard(self.figure):
            messagebox.showinfo("Копирование", "Копирование картинки в буфер работает только в Windows.\n"
                                "Используйте «Сохранить PNG».", parent=self)
