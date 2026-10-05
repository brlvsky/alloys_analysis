"""Палитра, шрифты, масштаб и стили в духе Windows 95.

Масштаб интерфейса = плотность экрана (DPI Windows: 100/125/150 %) × масштаб пользователя
(настройка «Масштаб интерфейса»; «Авто» — крупнее на больших мониторах). Все размеры в
пикселях считаются через px(), иконки увеличиваются целым числом раз (пиксель-арт без мыла).
"""
from __future__ import annotations

import math
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from ..core.settings import resource_dir

# --- палитра (часть 5 ТЗ)
FACE = "#C0C0C0"        # фон окон и панелей (button face)
LIGHT = "#FFFFFF"       # светлая кромка бевела
LIGHT2 = "#DFDFDF"      # полусветлая кромка
SHADOW = "#808080"      # тень
DARK = "#000000"        # тёмная тень
FIELD = "#FFFFFF"       # поля ввода, списки, таблицы
TEXT = "#000000"
SELECT_BG = "#000080"   # выделение
SELECT_FG = "#FFFFFF"
TITLE_BG = "#000080"    # заголовок панели
TITLE_FG = "#FFFFFF"
TOOLTIP_BG = "#FFFFE1"
FLAG_COLORS = {"ERROR": ("#FF0000", "#FFFFFF"), "WARN": ("#FFFF00", "#000000"), "INFO": ("#0000FF", "#FFFFFF")}

FONTS: dict[str, tuple] = {}
SCALE = {"dpi": 1.0, "user": 1.0, "total": 1.0}
USER_SCALES = [0, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0]   # 0 — «Авто»


def px(n: float) -> int:
    """Размер в пикселях с учётом масштаба."""
    return max(1, int(round(n * SCALE["total"])))


def setup_dpi() -> None:
    """Чёткие шрифты на мониторах 125–150 % (вызывать до создания Tk)."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001 — старые Windows
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:  # noqa: BLE001
                pass


def auto_user_scale(screen_w: int, screen_h: int, dpi: float) -> float:
    """Крупнее на больших мониторах: считаем «логический» размер экрана (в пикселях 100 %)."""
    w, h = screen_w / dpi, screen_h / dpi
    if w >= 3400 or h >= 1900:
        return 1.5
    if w >= 2400 or h >= 1350:     # 27″ 2560×1440 (или 4K при 150 %)
        return 1.25
    return 1.0


def _pick_family(fams: set[str]) -> str:
    # «Microsoft Sans Serif» — векторный двойник растрового MS Sans Serif: тот же рисунок,
    # но не рассыпается при увеличении. Растровый MS Sans Serif — только запасной вариант.
    for f in ("Microsoft Sans Serif", "Tahoma", "MS Sans Serif", "Arial", "Liberation Sans", "DejaVu Sans"):
        if f in fams:
            return f
    return "TkDefaultFont"


def apply(root: tk.Tk, user_scale: float = 0) -> None:
    """Применяет масштаб, шрифты и стили. user_scale: 0 — авто, иначе 1.0…2.0."""
    dpi = float(os.environ.get("PSD_LAB_DPI_SCALE", 0)) or max(1.0, root.winfo_fpixels("1i") / 96.0)
    user = user_scale or float(os.environ.get("PSD_LAB_UI_SCALE", 0)) or \
        auto_user_scale(root.winfo_screenwidth(), root.winfo_screenheight(), dpi)
    total = dpi * user
    SCALE.update(dpi=dpi, user=user, total=total)
    root.tk.call("tk", "scaling", 96.0 * total / 72.0)   # пунктов → пикселей

    fams = set(tkfont.families(root))
    fam = _pick_family(fams)
    mono = next((f for f in ("Courier New", "Liberation Mono", "DejaVu Sans Mono") if f in fams), "TkFixedFont")
    FONTS.update(ui=(fam, 8), bold=(fam, 8, "bold"), mono=(mono, 9), big=(fam, 12, "bold"),
                 readout=(fam, 10), readout_label=(fam, 8), small=(fam, 7))
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont",
                 "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
        try:
            tkfont.nametofont(name).configure(family=fam, size=8, weight="normal")
        except tk.TclError:
            pass
    ui = FONTS["ui"]

    root.configure(background=FACE)
    o = root.option_add
    o("*Background", FACE)
    o("*Foreground", TEXT)
    o("*Font", ui)
    o("*activeBackground", FACE)
    o("*selectBackground", SELECT_BG)
    o("*selectForeground", SELECT_FG)
    o("*highlightThickness", 0)
    o("*Entry.Background", FIELD)
    o("*Entry.relief", "sunken")
    o("*Entry.borderWidth", 2)
    o("*Listbox.Background", FIELD)
    o("*Text.Background", FIELD)
    o("*Spinbox.Background", FIELD)
    o("*Checkbutton.selectColor", FIELD)
    o("*Radiobutton.selectColor", FIELD)
    o("*Menu.activeBackground", SELECT_BG)
    o("*Menu.activeForeground", SELECT_FG)
    o("*Menu.relief", "raised")
    o("*Menu.borderWidth", 2)
    o("*Menu.activeBorderWidth", 0)
    o("*TCombobox*Listbox.background", FIELD)
    o("*TCombobox*Listbox.font", ui)

    bw = 2 if total < 2.5 else 3
    st = ttk.Style(root)
    st.theme_use("classic")
    st.configure(".", background=FACE, foreground=TEXT, font=ui, troughcolor=FACE,
                 selectbackground=SELECT_BG, selectforeground=SELECT_FG, fieldbackground=FIELD,
                 borderwidth=bw, highlightthickness=1, highlightcolor=DARK, lightcolor=LIGHT,
                 darkcolor=SHADOW, bordercolor=DARK, indicatordiameter=px(12), indicatorsize=px(12))
    st.configure("TButton", padding=(px(12), px(3)), relief="raised", anchor="center", width=-10,
                 shiftrelief=1, highlightthickness=0, defaultwidth=1)
    st.map("TButton", relief=[("pressed", "sunken")], background=[("active", FACE)])
    st.configure("Big.TButton", padding=(px(14), px(6)))
    st.configure("TFrame", background=FACE)
    st.configure("TLabel", background=FACE)
    st.configure("TLabelframe", relief="groove", borderwidth=2, background=FACE)
    st.configure("TLabelframe.Label", background=FACE, font=ui)
    st.configure("TNotebook", background=FACE, tabmargins=(px(2), px(3), px(2), 0), borderwidth=bw)
    st.configure("TNotebook.Tab", background=FACE, padding=(px(9), px(3)), borderwidth=bw, font=ui)
    st.map("TNotebook.Tab", background=[("selected", FACE)], expand=[("selected", (px(2), px(2), px(2), 0))],
           padding=[("selected", (px(9), px(4)))])
    line = tkfont.Font(root=root, font=ui).metrics("linespace")
    st.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT,
                 rowheight=max(line + px(5), icon_px() + px(3)), borderwidth=bw, relief="sunken", font=ui,
                 indent=px(18))
    st.map("Treeview", background=[("selected", SELECT_BG)], foreground=[("selected", SELECT_FG)])
    st.configure("Treeview.Heading", background=FACE, relief="raised", borderwidth=bw, font=ui,
                 padding=(px(4), px(2)))
    st.map("Treeview.Heading", relief=[("pressed", "sunken")], background=[("active", FACE)])
    st.configure("TScrollbar", background=FACE, troughcolor=LIGHT2, relief="raised", borderwidth=bw,
                 arrowsize=px(16), width=px(16))
    st.configure("TEntry", fieldbackground=FIELD, relief="sunken", borderwidth=2, padding=px(2))
    st.configure("TCombobox", fieldbackground=FIELD, background=FACE, arrowsize=px(14), padding=px(2))
    st.configure("TCheckbutton", background=FACE)
    st.configure("TRadiobutton", background=FACE)
    st.configure("TPanedwindow", background=FACE)
    st.configure("Sash", sashthickness=px(6), background=FACE, gripcount=0)


def fig_dpi() -> float:
    """dpi экранных графиков. Увеличение под масштаб matplotlib делает сам: берёт «device pixel
    ratio» из tk scaling (см. _backend_tk._update_device_pixel_ratio), поэтому здесь — базовые 96."""
    return 96.0


# --- иконки
_ICON_CACHE: dict = {}


def icon_px() -> int:
    """Мелкие иконки (дерево, кнопки графика): 16, 32, 48 — целое увеличение."""
    return 16 * max(1, math.floor(SCALE["total"] + 0.25))


def toolbar_px() -> int:
    """Иконки большого тулбара (нарисованы в 32×32): 32 до 175 %, дальше 64."""
    return 32 if SCALE["total"] < 1.75 else 64


def _icon_image(name: str, size: int):
    """PIL-картинка иконки нужного размера из исходника 16×16 (или 32×32 для значка программы)."""
    from PIL import Image

    base = resource_dir() / "assets" / "icons"
    # размеры, кратные 32, — из больших иконок (нарисованы отдельно), остальные — из 16×16
    src = base / f"{name}_32.png" if size % 32 == 0 else base / f"{name}_16.png"
    try:
        img = Image.open(src).convert("RGBA")
    except OSError:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if img.width != size:
        img = img.resize((size, size), Image.NEAREST if size % img.width == 0 else Image.LANCZOS)
    return img


def load_icon(root: tk.Misc, name: str, size: int | None = None):
    """PhotoImage иконки (кэшируется, ссылку держит кэш)."""
    from PIL import ImageTk

    size = size or icon_px()
    key = (name, size)
    if key not in _ICON_CACHE:
        _ICON_CACHE[key] = ImageTk.PhotoImage(_icon_image(name, size), master=root)
    return _ICON_CACHE[key]


def composite_icon(root: tk.Misc, names: list[str], size: int | None = None):
    """Несколько иконок в ряд (флажок + флаг качества) — для дерева образцов."""
    from PIL import Image, ImageTk

    size = size or icon_px()
    key = (tuple(names), size)
    if key not in _ICON_CACHE:
        gap = max(2, size // 8)
        img = Image.new("RGBA", (size * len(names) + gap * (len(names) - 1), size), (0, 0, 0, 0))
        for i, n in enumerate(names):
            part = _icon_image(n, size)
            img.paste(part, (i * (size + gap), 0), part)
        _ICON_CACHE[key] = ImageTk.PhotoImage(img, master=root)
    return _ICON_CACHE[key]


def scale_label(user_scale: float) -> str:
    return "Авто" if not user_scale else f"{user_scale * 100:.0f} %"
