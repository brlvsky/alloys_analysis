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
from ..hover import HoverInfo
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

        # ---- слой подсказок при наведении (курсор, точки, жёлтая подсказка) — через blitting
        self._hover_fn = None
        self._bg = None
        self._tip = None
        self._tip_rows = []
        self.canvas.mpl_connect("draw_event", self._on_draw)
        self.canvas.mpl_connect("motion_notify_event", self._on_move)
        self.canvas.mpl_connect("figure_leave_event", lambda e: self.hide_hover())
        self.canvas.get_tk_widget().bind("<Leave>", lambda e: self.hide_hover(), add="+")

    def set_title(self, text: str):
        self.title.configure(text=text)

    # ================================================================ подсказки при наведении
    def set_hover(self, fn):
        """fn(event) → HoverInfo | None; event.x, event.y — пиксели matplotlib (от левого нижнего угла)."""
        self._hover_fn = fn
        self.hide_hover()

    def _on_draw(self, _e=None):
        try:
            self._bg = self.canvas.copy_from_bbox(self.figure.bbox)
        except Exception:  # noqa: BLE001
            self._bg = None

    def _on_move(self, ev):
        if self._hover_fn is None or self._nav.mode.name in ("ZOOM", "PAN"):
            self.hide_hover()
            return
        try:
            info = self._hover_fn(ev)
        except Exception:  # noqa: BLE001 — подсказка не должна мешать работе
            info = None
        if info is None:
            self.hide_hover()
            return
        self.show_hover(info, ev.x, ev.y)

    def show_hover(self, info: HoverInfo, px_x: float, px_y: float):
        from matplotlib.patches import Rectangle

        if self._bg is None:
            self._on_draw()
        if self._bg is not None:
            self.canvas.restore_region(self._bg)
            artists = []
            for ax, x in info.vlines:
                artists.append(ax.axvline(x, color=theme.SELECT_BG, linewidth=1, linestyle="-", alpha=0.7,
                                          animated=True))
            for ax, x0, y0, w, h in info.rects:
                artists.append(ax.add_patch(Rectangle((x0, y0), w, h, facecolor=theme.SELECT_BG, alpha=0.25,
                                                      edgecolor=theme.SELECT_BG, linewidth=1.5, animated=True)))
            for ax, x, y, color in info.points:
                artists += ax.plot([x], [y], "o", markersize=7, markerfacecolor=color, markeredgecolor="black",
                                   markeredgewidth=1, animated=True)
            for a in artists:
                a.axes.draw_artist(a)
            self.canvas.blit(self.figure.bbox)
            for a in artists:
                a.remove()
        self._show_tip(info, px_x, self.figure.bbox.height - px_y)

    def _show_tip(self, info: HoverInfo, x: float, y: float):
        w = self.canvas.get_tk_widget()
        if self._tip is None:
            self._tip = tk.Frame(w, background=theme.TOOLTIP_BG, highlightthickness=1,
                                 highlightbackground=theme.DARK, highlightcolor=theme.DARK)
            self._tip_title = tk.Label(self._tip, background=theme.TOOLTIP_BG, font=theme.FONTS["bold"],
                                       anchor="w", padx=theme.px(4))
            self._tip_title.grid(row=0, column=0, columnspan=2, sticky="w")
        self._tip_title.configure(text=info.title)
        while len(self._tip_rows) < len(info.rows):
            i = len(self._tip_rows) + 1
            sw = tk.Frame(self._tip, width=theme.px(10), height=theme.px(10), highlightthickness=1,
                          highlightbackground=theme.DARK)
            lab = tk.Label(self._tip, background=theme.TOOLTIP_BG, anchor="w", padx=theme.px(3), pady=0)
            self._tip_rows.append((sw, lab, i))
        for k, (sw, lab, i) in enumerate(self._tip_rows):
            if k < len(info.rows):
                color, text = info.rows[k]
                if color:
                    sw.configure(background=color)
                    sw.grid(row=i, column=0, padx=(theme.px(4), 0))
                else:
                    sw.grid_remove()
                lab.configure(text=text)
                lab.grid(row=i, column=1, sticky="w", padx=(0, theme.px(4)))
            else:
                sw.grid_remove()
                lab.grid_remove()
        self._tip.update_idletasks()
        tw, th = self._tip.winfo_reqwidth(), self._tip.winfo_reqheight()
        ww, wh = w.winfo_width(), w.winfo_height()
        off = theme.px(16)
        tx = x + off if x + off + tw < ww else x - off - tw
        ty = y + off if y + off + th < wh else y - off - th
        self._tip.place(x=max(0, tx), y=max(0, ty))
        self._tip.lift()

    def hide_hover(self):
        if self._tip is not None:
            self._tip.place_forget()
        if self._bg is not None:
            try:
                self.canvas.restore_region(self._bg)
                self.canvas.blit(self.figure.bbox)
            except Exception:  # noqa: BLE001
                pass

    def hover_at(self, ax, x, y):
        """Показать подсказку в точке данных (для самопроверки и тестов). Возвращает HoverInfo."""
        from types import SimpleNamespace

        self.canvas.draw()
        px, py = ax.transData.transform((x, y))
        ev = SimpleNamespace(x=px, y=py, inaxes=ax)
        info = self._hover_fn(ev) if self._hover_fn else None
        if info is not None:
            self.show_hover(info, px, py)
        return info

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
        self.hide_hover()
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
