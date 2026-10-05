"""Перетаскивание файлов и папок на окно программы (расширение tkdnd через пакет tkinterdnd2).

Если расширение не загрузилось (нет пакета, другая версия Tcl), программа работает как раньше —
файлы открываются через меню и кнопки; причина пишется в журнал.
"""
from __future__ import annotations

from pathlib import Path


def enable(root, widgets, on_paths, on_hover=None, log=print) -> bool:
    """Регистрирует widgets как цели для перетаскивания файлов.

    on_paths(list[Path]) — вызывается после отпускания; on_hover(bool) — курсор с файлами над окном / ушёл.
    """
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD

        TkinterDnD._require(root)
    except Exception as e:  # noqa: BLE001 — без перетаскивания программа полностью работает
        log(f"Перетаскивание файлов недоступно ({type(e).__name__}: {e}); открывайте файлы через меню.")
        return False

    reg = TkinterDnD.DnDWrapper.drop_target_register
    bind = TkinterDnD.DnDWrapper.dnd_bind

    def drop(event):
        paths = parse_paths(root, event.data)
        if on_hover:
            on_hover(False)
        if paths:
            root.after_idle(lambda: on_paths(paths))
        return event.action

    def enter(event):
        if on_hover:
            on_hover(True)
        return event.action

    def leave(event):
        if on_hover:
            on_hover(False)
        return event.action

    n = 0
    for w in widgets:
        try:
            reg(w, DND_FILES)
            bind(w, "<<Drop>>", drop)
            bind(w, "<<DropEnter>>", enter)
            bind(w, "<<DropLeave>>", leave)
            n += 1
        except Exception as e:  # noqa: BLE001
            log(f"Перетаскивание: не удалось подключить {w}: {e}")
    return n > 0


def parse_paths(root, data: str) -> list[Path]:
    """Список путей из события tkdnd: Tcl-список, пути с пробелами — в фигурных скобках."""
    if not data:
        return []
    return [Path(p) for p in root.tk.splitlist(data) if p]
