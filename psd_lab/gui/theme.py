"""Палитра, шрифты и стили в духе Windows 95."""
from __future__ import annotations

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


def pick_fonts(root: tk.Misc) -> dict[str, tuple]:
    """MS Sans Serif 8 → Tahoma 8 → Arial 9 (→ DejaVu Sans 8 вне Windows); журнал — Courier New 9."""
    fams = set(tkfont.families(root))
    ui = next(((f, s) for f, s in (("MS Sans Serif", 8), ("Tahoma", 8), ("Arial", 9),
                                   ("DejaVu Sans", 8)) if f in fams), ("TkDefaultFont", 8))
    mono = next((f for f in ("Courier New", "Courier", "DejaVu Sans Mono") if f in fams), "TkFixedFont")
    FONTS.update(ui=ui, bold=(ui[0], ui[1], "bold"), mono=(mono, 9), big=(ui[0], ui[1] + 4, "bold"))
    return FONTS


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


def ui_scale(root: tk.Misc) -> float:
    """Во сколько раз экран плотнее 96 dpi (1.0, 1.25, 1.5 …)."""
    return max(1.0, root.winfo_fpixels("1i") / 96.0)


def apply(root: tk.Tk) -> None:
    if sys.platform == "win32":
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    f = pick_fonts(root)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont",
                 "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
        try:
            tkfont.nametofont(name).configure(family=f["ui"][0], size=f["ui"][1], weight="normal")
        except tk.TclError:
            pass

    root.configure(background=FACE)
    o = root.option_add
    o("*Background", FACE)
    o("*Foreground", TEXT)
    o("*Font", f["ui"])
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

    st = ttk.Style(root)
    st.theme_use("classic")
    st.configure(".", background=FACE, foreground=TEXT, font=f["ui"], troughcolor=FACE,
                 selectbackground=SELECT_BG, selectforeground=SELECT_FG, fieldbackground=FIELD,
                 borderwidth=2, highlightthickness=1, highlightcolor=DARK, lightcolor=LIGHT,
                 darkcolor=SHADOW, bordercolor=DARK)
    st.configure("TButton", padding=(10, 2), relief="raised", anchor="center", width=-9,
                 shiftrelief=1, highlightthickness=0, defaultwidth=1)
    st.map("TButton", relief=[("pressed", "sunken")], background=[("active", FACE)])
    st.configure("TFrame", background=FACE)
    st.configure("TLabel", background=FACE)
    st.configure("TLabelframe", relief="groove", borderwidth=2, background=FACE)
    st.configure("TLabelframe.Label", background=FACE, font=f["ui"])
    st.configure("TNotebook", background=FACE, tabmargins=(2, 2, 2, 0), borderwidth=2)
    st.configure("TNotebook.Tab", background=FACE, padding=(6, 2), borderwidth=2, font=f["ui"])
    st.map("TNotebook.Tab", background=[("selected", FACE)], expand=[("selected", (2, 2, 2, 0))],
           padding=[("selected", (6, 3))])
    row_h = tkfont.Font(root=root, font=f["ui"]).metrics("linespace") + 4
    icon = 32 if ui_scale(root) >= 1.75 else 16
    st.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT,
                 rowheight=max(row_h, icon + 2), borderwidth=2, relief="sunken", font=f["ui"])
    st.map("Treeview", background=[("selected", SELECT_BG)], foreground=[("selected", SELECT_FG)])
    st.configure("Treeview.Heading", background=FACE, relief="raised", borderwidth=2, font=f["ui"],
                 padding=(3, 1))
    st.map("Treeview.Heading", relief=[("pressed", "sunken")], background=[("active", FACE)])
    st.configure("TScrollbar", background=FACE, troughcolor=LIGHT2, relief="raised", borderwidth=2,
                 arrowsize=int(16 * ui_scale(root)))
    st.configure("TEntry", fieldbackground=FIELD, relief="sunken", borderwidth=2)
    st.configure("TCombobox", fieldbackground=FIELD, background=FACE, arrowsize=int(14 * ui_scale(root)))
    st.configure("TCheckbutton", background=FACE)
    st.configure("TRadiobutton", background=FACE)
    st.configure("TPanedwindow", background=FACE)
    st.configure("Sash", sashthickness=6, background=FACE)


# --- иконки
_ICON_CACHE: dict = {}


def icon_size(root: tk.Misc) -> int:
    return 32 if ui_scale(root) >= 1.75 else 16


def load_icon(root: tk.Misc, name: str, size: int | None = None):
    """PhotoImage иконки из assets/icons (кэшируется, ссылку держит кэш)."""
    from PIL import Image, ImageTk

    size = size or icon_size(root)
    key = (name, size)
    if key not in _ICON_CACHE:
        path = resource_dir() / "assets" / "icons" / f"{name}_{size}.png"
        try:
            img = Image.open(path).convert("RGBA")
        except OSError:
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        _ICON_CACHE[key] = ImageTk.PhotoImage(img, master=root)
    return _ICON_CACHE[key]


def composite_icon(root: tk.Misc, names: list[str], size: int | None = None):
    """Несколько иконок в ряд (флажок + флаг качества) — для дерева образцов."""
    from PIL import Image, ImageTk

    size = size or icon_size(root)
    key = (tuple(names), size)
    if key not in _ICON_CACHE:
        img = Image.new("RGBA", (size * len(names) + 2 * (len(names) - 1), size), (0, 0, 0, 0))
        for i, n in enumerate(names):
            p = resource_dir() / "assets" / "icons" / f"{n}_{size}.png"
            try:
                part = Image.open(p).convert("RGBA")
                img.paste(part, (i * (size + 2), 0), part)
            except OSError:
                pass
        _ICON_CACHE[key] = ImageTk.PhotoImage(img, master=root)
    return _ICON_CACHE[key]
