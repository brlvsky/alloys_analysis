"""Рисует пиксельные иконки 16×16 и 32×32 в 16-цветной палитре Windows (большие иконки тулбара
нарисованы отдельно, остальные 32×32 — увеличение 16×16 ×2),
а также assets/app.ico (16, 32, 48).

Запуск: python tools/make_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "icons"

# 16-цветная палитра Windows
K, M, G, O = (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0)
N, P, T, S = (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192)
D, R, L, Y = (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0)
B, F, A, W = (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)
PALETTE = [K, M, G, O, N, P, T, S, D, R, L, Y, B, F, A, W]


def canvas(size=16):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def px(d, pts, c):
    for x, y in pts:
        d.point((x, y), fill=c)


def glyph(d, rows, x0, y0, c):
    """Рисует пиксельный шрифт: rows — строки из '#' и '.'."""
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == "#":
                d.point((x0 + i, y0 + j), fill=c)


# ---------------------------------------------------------------- иконки 16×16
def folder(open_=False):
    img, d = canvas()
    d.rectangle((1, 3, 6, 5), fill=Y, outline=K)
    d.rectangle((1, 5, 14, 13), fill=Y if not open_ else O, outline=K)
    d.line((2, 4, 5, 4), fill=W)
    d.line((2, 6, 13, 6), fill=W)
    if open_:
        d.polygon([(4, 8), (15, 8), (12, 13), (1, 13)], fill=Y, outline=K)
        d.line((5, 9, 13, 9), fill=W)
    return img


def folder_docs():
    img, d = canvas()
    d.rectangle((1, 3, 6, 5), fill=Y, outline=K)
    d.rectangle((4, 1, 9, 8), fill=W, outline=K)
    d.rectangle((8, 2, 13, 8), fill=W, outline=K)
    d.line((9, 4, 12, 4), fill=D)
    d.line((9, 6, 12, 6), fill=D)
    d.rectangle((1, 6, 14, 13), fill=Y, outline=K)
    d.line((2, 7, 13, 7), fill=W)
    return img


def page(d, x0=2, y0=0, x1=13, y1=15):
    d.polygon([(x0, y0), (x1 - 3, y0), (x1, y0 + 3), (x1, y1), (x0, y1)], fill=W, outline=K)
    d.line((x1 - 3, y0, x1 - 3, y0 + 3), fill=K)
    d.line((x1 - 3, y0 + 3, x1, y0 + 3), fill=K)


def picture():
    img, d = canvas()
    d.rectangle((0, 2, 15, 13), fill=S, outline=K)
    d.rectangle((2, 4, 13, 11), fill=A, outline=D)
    d.rectangle((10, 5, 11, 6), fill=Y)
    d.polygon([(3, 11), (7, 6), (10, 9), (11, 8), (13, 11)], fill=G)
    return img


def report():
    img, d = canvas()
    page(d)
    d.line((4, 2, 8, 2), fill=N)
    d.line((4, 4, 9, 4), fill=D)
    for x, h in ((4, 3), (6, 6), (8, 4), (10, 2)):
        d.rectangle((x, 13 - h, x + 1, 13), fill=B)
    d.line((4, 7, 6, 6), fill=R)
    d.line((6, 6, 9, 9), fill=R)
    d.line((9, 9, 11, 10), fill=R)
    return img


def excel():
    img, d = canvas()
    d.rectangle((0, 1, 15, 14), fill=W, outline=K)
    d.rectangle((1, 2, 14, 4), fill=G)
    for x in (5, 10):
        d.line((x, 5, x, 13), fill=G)
    for y in (7, 10):
        d.line((1, y, 14, y), fill=G)
    glyph(d, ["#.#", ".#.", "#.#"], 2, 2, W)
    return img


def refresh():
    img, d = canvas()
    d.arc((2, 2, 13, 13), 200, 340, fill=G, width=2)
    d.arc((2, 2, 13, 13), 20, 160, fill=G, width=2)
    d.polygon([(10, 1), (14, 4), (10, 7)], fill=G)   # стрелка вправо сверху
    d.polygon([(5, 8), (1, 11), (5, 14)], fill=G)    # стрелка влево снизу
    return img


def gear():
    img, d = canvas()
    for x, y in ((7, 0), (7, 13), (0, 7), (13, 7), (2, 2), (12, 2), (2, 12), (12, 12)):
        d.rectangle((x, y, x + 1 if x in (7, 0, 13) or y in (0, 13) else x + 1, y + 1 if True else y), fill=D)
    d.ellipse((2, 2, 13, 13), fill=S, outline=K)
    d.ellipse((5, 5, 10, 10), fill=W, outline=K)
    for x, y in ((7, 0), (8, 0), (7, 15), (8, 15), (0, 7), (0, 8), (15, 7), (15, 8)):
        d.point((x, y), fill=K)
    px(d, [(2, 2), (13, 2), (2, 13), (13, 13), (3, 2), (2, 3), (12, 2), (13, 3), (2, 12), (3, 13), (13, 12), (12, 13)], K)
    d.line((5, 5, 6, 6), fill=D)
    return img


QUESTION = [
    ".####.",
    "##..##",
    "....##",
    "...##.",
    "..##..",
    "..##..",
    "......",
    "..##..",
]


def help_():
    img, d = canvas()
    d.ellipse((0, 0, 15, 15), fill=Y, outline=K)
    glyph(d, QUESTION, 5, 3, N)
    return img


def flag_error():
    img, d = canvas()
    d.ellipse((0, 0, 15, 15), fill=R, outline=M)
    for k in range(-1, 1):
        d.line((4 + k + 1, 4, 11 + k + 1, 11), fill=W)
        d.line((11 + k + 1, 4, 4 + k + 1, 11), fill=W)
    return img


def flag_warn():
    img, d = canvas()
    d.polygon([(7, 0), (8, 0), (15, 14), (0, 14)], fill=Y, outline=K)
    d.rectangle((7, 4, 8, 9), fill=K)
    d.rectangle((7, 11, 8, 12), fill=K)
    return img


def flag_info():
    img, d = canvas()
    d.ellipse((0, 0, 15, 15), fill=B, outline=N)
    d.rectangle((7, 3, 8, 4), fill=W)
    d.rectangle((7, 6, 8, 12), fill=W)
    d.line((6, 6, 7, 6), fill=W)
    d.line((6, 12, 9, 12), fill=W)
    return img


def ok():
    img, d = canvas()
    d.line((2, 8, 6, 12), fill=G, width=3)
    d.line((6, 12, 13, 3), fill=G, width=3)
    return img


def cross():
    img, d = canvas()
    d.line((3, 3, 12, 12), fill=R, width=3)
    d.line((12, 3, 3, 12), fill=R, width=3)
    return img


def checkbox(checked: bool):
    img, d = canvas()
    d.rectangle((1, 1, 13, 13), fill=W)
    d.line((1, 1, 12, 1), fill=D)
    d.line((1, 1, 1, 12), fill=D)
    d.line((2, 2, 11, 2), fill=K)
    d.line((2, 2, 2, 11), fill=K)
    d.line((1, 13, 13, 13), fill=W)
    d.line((13, 1, 13, 13), fill=W)
    d.line((2, 12, 12, 12), fill=S)
    d.line((12, 2, 12, 12), fill=S)
    if checked:
        for k in range(3):
            d.line((4, 6 + k, 6, 8 + k), fill=K)
            d.line((6, 8 + k, 10, 4 + k), fill=K)
    return img


def zoom():
    img, d = canvas()
    d.ellipse((1, 1, 10, 10), fill=W, outline=K)
    d.arc((3, 3, 8, 8), 180, 270, fill=A)
    d.line((9, 9, 14, 14), fill=K, width=3)
    d.line((5, 3, 5, 8), fill=K)
    d.line((3, 5, 8, 5), fill=K)
    return img


def pan():
    img, d = canvas()
    d.line((7, 1, 7, 14), fill=K)
    d.line((1, 7, 14, 7), fill=K)
    for pts in ([(7, 0), (4, 3), (10, 3)], [(7, 15), (4, 12), (10, 12)],
                [(0, 7), (3, 4), (3, 10)], [(15, 7), (12, 4), (12, 10)]):
        d.polygon(pts, fill=K)
    return img


def home():
    img, d = canvas()
    d.polygon([(7, 1), (8, 1), (15, 8), (0, 8)], fill=R, outline=M)
    d.rectangle((2, 8, 13, 14), fill=W, outline=K)
    d.rectangle((6, 10, 9, 14), fill=O, outline=K)
    return img


def copy():
    img, d = canvas()
    page(d, 0, 0, 9, 11)
    page(d, 6, 4, 15, 15)
    for y in (8, 10, 12):
        d.line((8, y, 13, y), fill=D)
    return img


def save():
    img, d = canvas()
    d.rectangle((0, 0, 15, 15), fill=N, outline=K)
    d.rectangle((3, 1, 12, 7), fill=W)
    d.line((4, 3, 11, 3), fill=D)
    d.line((4, 5, 11, 5), fill=D)
    d.rectangle((4, 10, 11, 15), fill=S)
    d.rectangle((9, 11, 10, 14), fill=N)
    return img


def document():
    img, d = canvas()
    page(d)
    for y in (5, 7, 9, 11):
        d.line((4, y, 11, y), fill=D)
    return img


def sheet_chart():
    """Файл с данными прибора: лист с кривой."""
    img, d = canvas()
    page(d)
    d.line((4, 12, 4, 4), fill=K)
    d.line((4, 12, 11, 12), fill=K)
    px(d, [(5, 11), (6, 10), (7, 8), (8, 6), (9, 5), (10, 5)], R)
    return img


def blank():
    return canvas()[0]


# ---------------------------------------------------------------- значок приложения
def app_icon(size=32):
    """Колба Эрленмейера с графиком распределения (столбики + накопленная кривая)."""
    s = size / 32
    img, d = canvas(32)
    # колба
    d.polygon([(12, 2), (19, 2), (19, 10), (29, 28), (29, 30), (2, 30), (2, 28), (12, 10)], fill=W, outline=K)
    d.rectangle((11, 1, 20, 3), fill=S, outline=K)
    # жидкость
    d.polygon([(8, 19), (23, 19), (28, 28), (28, 29), (3, 29), (3, 28)], fill=A)
    d.line((8, 19, 23, 19), fill=T)
    # столбики распределения
    for x, h in ((7, 3), (10, 7), (13, 9), (16, 6), (19, 4), (22, 2)):
        d.rectangle((x, 28 - h, x + 2, 28), fill=N)
    # накопленная кривая
    d.line([(5, 28), (9, 26), (12, 22), (15, 17), (18, 14), (22, 12), (26, 11)], fill=R, width=2)
    # блик
    d.line((14, 5, 14, 9), fill=S)
    if size != 32:
        img = img.resize((size, size), Image.NEAREST if size % 32 == 0 else Image.LANCZOS)
    del s
    return img


def app_icon_16():
    img, d = canvas()
    d.polygon([(6, 1), (9, 1), (9, 5), (14, 13), (14, 14), (1, 14), (1, 13), (6, 5)], fill=W, outline=K)
    d.polygon([(4, 9), (11, 9), (13, 13), (2, 13)], fill=A)
    for x, h in ((4, 1), (6, 3), (8, 2), (10, 1)):
        d.rectangle((x, 13 - h, x + 1, 13), fill=N)
    d.line([(3, 13), (6, 10), (8, 8), (12, 7)], fill=R)
    return img


ICONS = {
    "open": lambda: folder(open_=True),
    "folder": folder,
    "open_dir": folder_docs,
    "export_png": picture,
    "report": report,
    "excel": excel,
    "refresh": refresh,
    "settings": gear,
    "help": help_,
    "flag_error": flag_error,
    "flag_warn": flag_warn,
    "flag_info": flag_info,
    "ok": ok,
    "cross": cross,
    "check_on": lambda: checkbox(True),
    "check_off": lambda: checkbox(False),
    "zoom": zoom,
    "pan": pan,
    "home": home,
    "copy": copy,
    "save": save,
    "document": document,
    "sample": sheet_chart,
    "blank": blank,
    "app": app_icon_16,
}


# ---------------------------------------------------------------- большие иконки 32×32
# Рисуются отдельно (как большие иконки Win95), а не увеличением 16×16: чёрный контур,
# белый блик сверху-слева, тёмная тень снизу-справа, 16 цветов.
import math  # noqa: E402


def c32():
    return canvas(32)


def bevel_rect(d, box, fill, light=W, shadow=O, outline=K):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=fill, outline=outline)
    d.line((x0 + 1, y0 + 1, x1 - 1, y0 + 1), fill=light)
    d.line((x0 + 1, y0 + 1, x0 + 1, y1 - 1), fill=light)
    d.line((x0 + 1, y1 - 1, x1 - 1, y1 - 1), fill=shadow)
    d.line((x1 - 1, y0 + 2, x1 - 1, y1 - 1), fill=shadow)


def page32(d, x0, y0, x1, y1, fold=7):
    d.polygon([(x0, y0), (x1 - fold, y0), (x1, y0 + fold), (x1, y1), (x0, y1)], fill=W, outline=K)
    d.polygon([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill=S, outline=K)
    d.line((x1 - 1, y0 + fold + 1, x1 - 1, y1 - 1), fill=S)
    d.line((x0 + 1, y1 - 1, x1 - 1, y1 - 1), fill=S)


def folder32(open_=False):
    img, d = c32()
    d.polygon([(2, 7), (4, 5), (12, 5), (14, 7)], fill=Y, outline=K)          # язычок
    d.line((4, 6, 12, 6), fill=W)
    if not open_:
        bevel_rect(d, (1, 7, 28, 27), Y)
        d.line((2, 10, 27, 10), fill=O)                                     # кромка крышки
        d.line((2, 11, 27, 11), fill=W)
        d.line((2, 28, 29, 28), fill=D)                                     # тень
        d.line((29, 8, 29, 28), fill=D)
    else:
        bevel_rect(d, (1, 7, 26, 27), O, light=Y, shadow=K)
        d.polygon([(7, 13), (31, 13), (26, 27), (1, 27)], fill=Y, outline=K)
        d.line((8, 14, 29, 14), fill=W)
        d.line((7, 14, 2, 26), fill=W)
        d.line((25, 26, 29, 15), fill=O)
    return img


def folder_docs32():
    img, d = c32()
    d.polygon([(2, 7), (4, 5), (12, 5), (14, 7)], fill=Y, outline=K)
    page32(d, 6, 1, 18, 16, fold=4)
    page32(d, 13, 3, 25, 17, fold=4)
    for y in (8, 10, 12):
        d.line((15, y, 22, y), fill=D)
    for y in (6, 8):
        d.line((8, y, 13, y), fill=D)
    bevel_rect(d, (1, 12, 28, 27), Y)
    d.line((2, 15, 27, 15), fill=O)
    d.line((2, 28, 29, 28), fill=D)
    d.line((29, 13, 29, 28), fill=D)
    return img


def chart_page32():
    img, d = c32()
    page32(d, 4, 1, 27, 30)
    d.line((8, 7, 8, 25), fill=K)
    d.line((8, 25, 24, 25), fill=K)
    for x, h in ((10, 3), (13, 8), (16, 11), (19, 6), (22, 3)):
        d.rectangle((x, 25 - h, x + 1, 24), fill=B)
    d.line([(9, 24), (12, 22), (15, 16), (18, 11), (21, 9), (24, 8)], fill=R, width=2)
    return img


def picture32():
    img, d = c32()
    bevel_rect(d, (0, 3, 31, 28), S, light=W, shadow=D)
    d.rectangle((3, 6, 28, 25), fill=A, outline=K)
    d.rectangle((4, 7, 27, 12), fill=W)
    d.rectangle((4, 13, 27, 15), fill=A)
    d.ellipse((20, 8, 25, 13), fill=Y, outline=O)
    d.polygon([(4, 25), (11, 14), (16, 20), (19, 17), (27, 25)], fill=G)
    d.polygon([(11, 14), (13, 17), (9, 17)], fill=W)
    d.line([(4, 24), (11, 15)], fill=L)
    return img


def report32():
    img, d = c32()
    page32(d, 3, 0, 28, 31)
    d.rectangle((6, 3, 18, 5), fill=N)
    for y in (8, 10):
        d.line((6, y, 24, y), fill=D)
    d.rectangle((6, 13, 25, 27), fill=W, outline=D)
    for x, h in ((8, 4), (11, 9), (14, 12), (17, 7), (20, 4)):
        d.rectangle((x, 26 - h, x + 1, 26), fill=B)
    d.line([(7, 25), (10, 23), (13, 18), (16, 15), (19, 14), (24, 13)], fill=R, width=2)
    return img


def excel32():
    img, d = c32()
    d.rectangle((2, 2, 30, 29), fill=W, outline=K)
    d.rectangle((3, 3, 29, 6), fill=G)
    d.rectangle((3, 7, 7, 28), fill=S)
    for x in (7, 14, 21):
        d.line((x, 7, x, 28), fill=D)
    for y in (11, 15, 19, 23):
        d.line((3, y, 29, y), fill=D)
    d.line((3, 7, 29, 7), fill=K)
    d.rectangle((15, 16, 20, 18), fill=Y, outline=K)                          # выделенная ячейка
    # зелёный значок «X»
    d.rectangle((0, 17, 12, 31), fill=G, outline=K)
    for k in range(2):
        d.line((3 + k, 20, 8 + k, 28), fill=W)
        d.line((8 + k, 20, 3 + k, 28), fill=W)
    return img


def refresh32():
    img, d = c32()
    for width, col in ((7, K), (4, L)):
        d.arc((4, 4, 27, 27), 200, 345, fill=col, width=width)
        d.arc((4, 4, 27, 27), 20, 165, fill=col, width=width)
    d.arc((5, 5, 26, 26), 205, 340, fill=G, width=1)
    d.arc((5, 5, 26, 26), 25, 160, fill=G, width=1)
    d.polygon([(21, 1), (31, 8), (20, 13)], fill=L, outline=K)               # стрелка сверху
    d.polygon([(11, 30), (1, 23), (12, 18)], fill=L, outline=K)              # стрелка снизу
    return img


def gear32():
    img, d = c32()
    cx = cy = 15.5
    pts = []
    for i in range(32):
        a = 2 * math.pi * i / 32
        r = 15 if (i // 2) % 2 == 0 else 11.5
        pts.append((cx + r * math.cos(a + math.pi / 32), cy + r * math.sin(a + math.pi / 32)))
    d.polygon(pts, fill=S, outline=K)
    d.ellipse((6, 6, 25, 25), fill=S, outline=D)
    d.arc((6, 6, 25, 25), 135, 315, fill=W)
    d.ellipse((11, 11, 20, 20), fill=D, outline=K)
    d.arc((11, 11, 20, 20), 315, 135, fill=W)
    return img


def help32():
    img, d = c32()
    d.ellipse((1, 1, 30, 30), fill=Y, outline=K)
    d.arc((3, 3, 28, 28), 130, 300, fill=W, width=2)
    d.arc((3, 3, 28, 28), 310, 120, fill=O, width=2)
    q = ["..####..", ".##..##.", "......##", ".....##.", "....##..", "...##...", "...##...",
         "........", "...##...", "...##..."]
    for j, row in enumerate(q):
        for i, ch in enumerate(row):
            if ch == "#":
                d.rectangle((8 + i * 2, 5 + j * 2, 9 + i * 2, 6 + j * 2), fill=N)
    return img


def zoom32():
    img, d = c32()
    d.line((19, 19, 29, 29), fill=K, width=7)
    d.line((20, 20, 28, 28), fill=M, width=3)
    d.ellipse((1, 1, 22, 22), fill=S, outline=K)
    d.ellipse((4, 4, 19, 19), fill=W, outline=K)
    d.arc((6, 6, 17, 17), 190, 260, fill=A, width=2)
    d.rectangle((11, 7, 12, 16), fill=K)
    d.rectangle((7, 11, 16, 12), fill=K)
    return img


def pan32():
    img, d = c32()
    d.rectangle((14, 5, 17, 26), fill=K)
    d.rectangle((5, 14, 26, 17), fill=K)
    for pts in ([(15.5, 0), (9, 7), (22, 7)], [(15.5, 31), (9, 24), (22, 24)],
                [(0, 15.5), (7, 9), (7, 22)], [(31, 15.5), (24, 9), (24, 22)]):
        d.polygon(pts, fill=K)
    d.rectangle((13, 13, 18, 18), fill=W, outline=K)
    return img


def home32():
    img, d = c32()
    d.rectangle((21, 3, 24, 10), fill=M, outline=K)                          # труба
    d.polygon([(15.5, 2), (31, 15), (0, 15)], fill=R, outline=K)
    d.line((15, 4, 3, 14), fill=W)
    bevel_rect(d, (4, 15, 27, 29), W, light=W, shadow=S)
    d.rectangle((7, 18, 13, 23), fill=A, outline=K)
    d.line((10, 18, 10, 23), fill=K)
    d.line((7, 20, 13, 20), fill=K)
    d.rectangle((17, 19, 23, 29), fill=O, outline=K)
    d.point((21, 24), fill=Y)
    return img


def copy32():
    img, d = c32()
    page32(d, 1, 1, 18, 22, fold=5)
    for y in (8, 11, 14, 17):
        d.line((4, y, 14, y), fill=D)
    page32(d, 12, 9, 30, 30, fold=5)
    for y in (16, 19, 22, 25):
        d.line((15, y, 26, y), fill=N)
    return img


def save32():
    img, d = c32()
    d.polygon([(1, 1), (27, 1), (30, 4), (30, 30), (1, 30)], fill=N, outline=K)
    d.rectangle((6, 2, 25, 13), fill=W, outline=K)
    for y in (5, 8, 11):
        d.line((8, y, 23, y), fill=D)
    bevel_rect(d, (7, 18, 24, 30), S, light=W, shadow=D)
    d.rectangle((17, 20, 21, 27), fill=N)
    d.line((2, 2, 2, 29), fill=B)
    return img


ICONS32 = {
    "open": lambda: folder32(open_=True),
    "folder": folder32,
    "open_dir": folder_docs32,
    "sample": chart_page32,
    "export_png": picture32,
    "report": report32,
    "excel": excel32,
    "refresh": refresh32,
    "settings": gear32,
    "help": help32,
    "zoom": zoom32,
    "pan": pan32,
    "home": home32,
    "copy": copy32,
    "save": save32,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in ICONS.items():
        img16 = fn()
        img16.save(OUT / f"{name}_16.png")
        if name == "app":
            app_icon(32).save(OUT / "app_32.png")
        elif name in ICONS32:
            ICONS32[name]().save(OUT / f"{name}_32.png")
        else:
            img16.resize((32, 32), Image.NEAREST).save(OUT / f"{name}_32.png")
    big = app_icon(32)
    ico_imgs = [app_icon_16(), big, big.resize((48, 48), Image.NEAREST)]
    ico_imgs[1].save(ROOT / "assets" / "app.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                     append_images=[ico_imgs[0], ico_imgs[2]])
    # лист-образец для проверки глазами
    names = list(ICONS)
    sheet = Image.new("RGB", (len(names) * 40 + 40, 80), S)
    for i, n in enumerate(names):
        sheet.paste(Image.open(OUT / f"{n}_32.png"), (8 + i * 40, 8), Image.open(OUT / f"{n}_32.png"))
        sheet.paste(Image.open(OUT / f"{n}_16.png"), (16 + i * 40, 52), Image.open(OUT / f"{n}_16.png"))
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    sheet.save(ROOT / "tools" / "icons_preview.png")
    print(f"Иконок: {len(names)} → {OUT}; app.ico готов")


if __name__ == "__main__":
    main()
