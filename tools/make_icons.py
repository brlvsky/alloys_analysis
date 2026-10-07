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


# ---------------------------------------------------------------- фигуры по маске
# Ровные круглые формы (шестерёнка, круговые стрелки): фигура задаётся функцией «точка внутри?»,
# пиксель закрашивается, если внутри не меньше половины его площади; дальше — объём как у
# иконок Win95: чёрный контур, светлая кромка сверху-слева, тень снизу-справа.
import math  # noqa: E402


def mask_from(inside, size, ss=4):
    m = [[False] * size for _ in range(size)]
    for y in range(size):
        for x in range(size):
            hit = sum(inside(x + (i + 0.5) / ss, y + (j + 0.5) / ss) for j in range(ss) for i in range(ss))
            m[y][x] = hit * 2 >= ss * ss
    return m


def bevel_shape(m, fill, light, shadow, outline=K, width=2):
    """width=2 — кромка в 1 px внутри контура (32×32); width=1 — для мелких иконок 16×16."""
    n = len(m)
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    inside = lambda x, y: 0 <= x < n and 0 <= y < n and m[y][x]  # noqa: E731
    edge = lambda x, y: inside(x, y) and not (inside(x - 1, y) and inside(x + 1, y)  # noqa: E731
                                              and inside(x, y - 1) and inside(x, y + 1))
    for y in range(n):
        for x in range(n):
            if not m[y][x]:
                continue
            if edge(x, y):
                c = outline
            elif width == 1:
                c = shadow if edge(x + 1, y) or edge(x, y + 1) else light if edge(x - 1, y) or edge(x, y - 1) else fill
            elif not (inside(x - 2, y) and inside(x, y - 2)) or not inside(x - 1, y - 1):
                c = light
            elif not (inside(x + 2, y) and inside(x, y + 2)) or not inside(x + 1, y + 1):
                c = shadow
            else:
                c = fill
            img.putpixel((x, y), c + (255,))
    return img


def in_triangle(x, y, a, b, c):
    def side(p, q, r):
        return (p[0] - r[0]) * (q[1] - r[1]) - (q[0] - r[0]) * (p[1] - r[1])
    d = (side((x, y), a, b), side((x, y), b, c), side((x, y), c, a))
    return not (min(d) < 0 < max(d))


def gear_shape(size, R, r_root, teeth, tip_half, root_half, hole):
    """Шестерёнка: зубцы-трапеции (полуширина вершины и основания — в градусах), отверстие в центре."""
    c, period = size / 2, 360 / teeth

    def inside(x, y):
        r = math.hypot(x - c, y - c)
        a = abs((math.degrees(math.atan2(y - c, x - c)) + period / 2) % period - period / 2)
        if a <= tip_half:
            lim = R
        elif a <= root_half:
            lim = R - (R - r_root) * (a - tip_half) / (root_half - tip_half)
        else:
            lim = r_root
        return hole <= r <= lim
    return inside


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


def word():
    """Документ Word: лист с текстом и синий значок «W»."""
    img, d = canvas()
    d.polygon([(3, 0), (11, 0), (14, 3), (14, 15), (3, 15)], fill=W, outline=K)
    d.line((11, 0, 11, 3), fill=K)
    d.line((11, 3, 14, 3), fill=K)
    for y in (5, 7, 9, 11, 13):
        d.line((9, y, 12, y), fill=D)
    d.rectangle((0, 4, 8, 12), fill=N, outline=K)
    glyph(d, ["#...#", "#...#", "#.#.#", "#.#.#", ".#.#."], 2, 6, W)
    return img


# «Обновить»: две зелёные стрелки по кругу, нарисованы по пикселям (верхняя половина;
# нижняя — та же, повёрнутая на 180°)
REFRESH16_TOP = [
    "......KKKK......",
    "....KKLLLLKK.K..",
    "...KLLGGGGLLKLK.",
    "..KLGK....KGLLK.",
    "..KLK....KLLLLK.",
    ".KLGK...KKKKKKK.",
    ".KLK............",
    ".KLK............",
]


def refresh():
    top = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    for y, row in enumerate(REFRESH16_TOP):
        for x, ch in enumerate(row):
            if ch != ".":
                top.putpixel((x, y), {"K": K, "L": L, "G": G}[ch] + (255,))
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    img.paste(top, (0, 0))
    img.paste(top.rotate(180), (0, 8))
    return img


def gear():
    return bevel_shape(mask_from(gear_shape(16, 7.9, 5.6, 8, 10, 16, 2.1), 16), S, W, D, width=1)


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



# ---------------------------------------------------------------- иконки вкладок 16×16
def tab_dist():
    img, d = canvas()
    d.rectangle((0, 0, 15, 15), fill=W, outline=K)
    for x, h in ((2, 3), (4, 7), (6, 9), (8, 6), (10, 4), (12, 2)):
        d.rectangle((x, 14 - h, x + 1, 14), fill=D)
    d.line([(1, 13), (4, 9), (7, 4), (10, 2), (14, 1)], fill=R)
    return img


def tab_cmp():
    img, d = canvas()
    d.rectangle((0, 0, 15, 15), fill=W, outline=K)
    d.line([(1, 14), (4, 12), (6, 5), (9, 2), (14, 1)], fill=B)
    d.line([(1, 14), (6, 13), (9, 8), (11, 4), (14, 2)], fill=R)
    d.line([(1, 14), (8, 13), (11, 11), (13, 6), (14, 4)], fill=G)
    return img


def tab_sum():
    img, d = canvas()
    d.rectangle((0, 1, 15, 14), fill=W, outline=K)
    d.rectangle((1, 2, 14, 4), fill=N)
    for y in (7, 10):
        d.line((1, y, 14, y), fill=D)
    for x in (5, 10):
        d.line((x, 5, x, 13), fill=D)
    return img


def tab_pop():
    img, d = canvas()
    import math
    for cx, s, h, col in ((5, 1.8, 11, B), (11, 1.6, 8, R)):
        pts = [(x, 14 - h * math.exp(-((x - cx) / s) ** 2 / 2)) for x in range(0, 16)]
        d.line(pts, fill=col, width=1)
    d.line((0, 15, 15, 15), fill=K)
    return img


def tab_tech():
    img, d = canvas()
    for y, col in ((10, S), (12, D), (14, K)):
        d.rectangle((1, y, 14, y + 1), fill=col)
    d.line((1, 10, 14, 10), fill=W)
    d.polygon([(6, 0), (9, 0), (8, 8), (7, 8)], fill=R)
    d.rectangle((5, 8, 10, 9), fill=Y)
    return img


def tab_surf():
    img, d = canvas()
    d.ellipse((1, 1, 14, 14), fill=S, outline=K)
    d.ellipse((3, 3, 7, 7), fill=W)
    for x, y in ((9, 5), (11, 9), (6, 11), (9, 12), (4, 9)):
        d.point((x, y), fill=R)
        d.point((x + 1, y), fill=R)
    return img


def tab_pack():
    img, d = canvas()
    for x, y in ((0, 8), (8, 8), (4, 1)):
        d.ellipse((x, y, x + 7, y + 7), fill=S, outline=K)
    for x, y in ((7, 6), (3, 13), (12, 13)):
        d.ellipse((x, y, x + 2, y + 2), fill=O)
    return img


def tab_kin():
    img, d = canvas()
    d.rectangle((3, 0, 12, 1), fill=O)
    d.rectangle((3, 14, 12, 15), fill=O)
    d.polygon([(4, 2), (11, 2), (8, 8), (11, 13), (4, 13), (7, 8)], fill=W, outline=K)
    d.polygon([(5, 3), (10, 3), (8, 6), (7, 6)], fill=Y)
    d.polygon([(5, 12), (10, 12), (8, 10), (7, 10)], fill=Y)
    return img


def tab_db():
    img, d = canvas()
    d.rectangle((2, 3, 13, 13), fill=S)
    d.line((2, 3, 2, 13), fill=K)
    d.line((13, 3, 13, 13), fill=K)
    for y in (8, 13):
        d.arc((2, y - 2, 13, y + 2), 0, 180, fill=K)
    d.ellipse((2, 1, 13, 5), fill=W, outline=K)
    d.point((10, 10), fill=L)
    return img


def tab_method():
    img, d = canvas()
    d.polygon([(1, 2), (7, 3), (7, 15), (1, 14)], fill=W, outline=K)
    d.polygon([(8, 3), (14, 2), (14, 14), (8, 15)], fill=W, outline=K)
    d.rectangle((7, 3, 8, 15), fill=N)
    for y in (6, 8, 10):
        d.line((2, y, 6, y + 0), fill=D)
        d.line((9, y, 13, y), fill=D)
    return img


def tab_charge():
    """Весы с чашами — расчёт шихты (навески)."""
    img, d = canvas()
    d.line((8, 2, 8, 12), fill=K)            # стойка
    d.line((3, 4, 13, 4), fill=K)            # коромысло
    d.point((8, 2), fill=K)
    d.line((3, 4, 1, 8), fill=D)             # подвесы
    d.line((3, 4, 5, 8), fill=D)
    d.line((13, 4, 11, 8), fill=D)
    d.line((13, 4, 15, 8), fill=D)
    d.line((1, 8, 5, 8), fill=K)             # чаши
    d.line((11, 8, 15, 8), fill=K)
    d.rectangle((6, 12, 10, 14), fill=S, outline=K)   # основание
    d.point((2, 7), fill=O)                  # порошок в чашах
    d.point((3, 7), fill=O)
    d.point((12, 7), fill=N)
    d.point((13, 7), fill=N)
    return img


def bulb32():
    """Лампочка для «Знаете ли вы…?» (как в окне приветствия Windows 95)."""
    img, d = canvas(32)
    for a in range(0, 360, 45):
        import math
        x, y = 16 + 14 * math.cos(math.radians(a)), 12 + 11 * math.sin(math.radians(a))
        d.line((16 + 11 * math.cos(math.radians(a)), 12 + 9 * math.sin(math.radians(a)), x, y), fill=Y, width=2)
    d.ellipse((8, 3, 24, 20), fill=Y, outline=K)
    d.ellipse((11, 6, 15, 10), fill=W)
    d.polygon([(12, 18), (20, 18), (19, 23), (13, 23)], fill=Y, outline=K)
    for y in (24, 26, 28):
        d.rectangle((12, y, 20, y + 1), fill=D, outline=K)
    d.line((15, 30, 17, 30), fill=K)
    return img

ICONS = {
    "open": lambda: folder(open_=True),
    "folder": folder,
    "open_dir": folder_docs,
    "export_png": picture,
    "report": report,
    "excel": excel,
    "word": word,
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
    "tab_dist": tab_dist, "tab_cmp": tab_cmp, "tab_sum": tab_sum, "tab_pop": tab_pop, "tab_tech": tab_tech,
    "tab_surf": tab_surf, "tab_pack": tab_pack, "tab_kin": tab_kin, "tab_db": tab_db, "tab_method": tab_method, "tab_charge": tab_charge,
}


# ---------------------------------------------------------------- большие иконки 32×32
# Рисуются отдельно (как большие иконки Win95), а не увеличением 16×16: чёрный контур,
# белый блик сверху-слева, тёмная тень снизу-справа, 16 цветов.


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


def word32():
    img, d = c32()
    page32(d, 7, 0, 29, 31)
    for y in (8, 11, 14, 17, 20, 23, 26):
        d.line((19, y, 26, y), fill=D)
    d.line((10, 5, 20, 5), fill=D)
    bevel_rect(d, (0, 7, 17, 24), N, light=B, shadow=K)
    w = ["##.....##", "##.....##", "##..#..##", "##.###.##", "##.###.##", ".###.###.", ".##...##.", ".#.....#."]
    for j, row in enumerate(w):
        for i, ch in enumerate(row):
            if ch == "#":
                d.point((4 + i, 11 + j), fill=W)
    return img


def refresh32():
    c = 16.0

    def half(x, y):   # дуга сверху + наконечник справа; вторая половина — поворот на 180°
        r = math.hypot(x - c, y - c)
        ang = math.degrees(math.atan2(y - c, x - c)) % 360
        if 7.6 <= r <= 12.4 and 178 <= ang <= 322:
            return True
        return in_triangle(x, y, (29.5, 4.0), (29.5, 14.6), (18.9, 14.6))

    return bevel_shape(mask_from(lambda x, y: half(x, y) or half(32 - x, 32 - y), 32), L, W, G)


def gear32():
    img = bevel_shape(mask_from(gear_shape(32, 15.4, 11.2, 8, 9, 15, 4.6), 32), S, W, D)
    for y in range(32):   # кольцевая канавка вокруг ступицы (тень сверху-слева, блик снизу-справа)
        for x in range(32):
            dx, dy = x + 0.5 - 16, y + 0.5 - 16
            if 7.0 <= math.hypot(dx, dy) < 8.0 and img.getpixel((x, y))[3]:
                img.putpixel((x, y), (D if dx + dy < 0 else W) + (255,))
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
    "word": word32,
    "refresh": refresh32,
    "settings": gear32,
    "help": help32,
    "zoom": zoom32,
    "pan": pan32,
    "home": home32,
    "copy": copy32,
    "save": save32,
    "bulb": bulb32,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ICONS.setdefault("bulb", lambda: bulb32().resize((16, 16), Image.LANCZOS))
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
