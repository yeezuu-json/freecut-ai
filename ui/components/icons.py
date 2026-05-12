# my_app/ui/icons.py

from pathlib import Path

import qtawesome as qta
from PySide6.QtGui import QIcon, QColor


BASE_DIR = Path(__file__).resolve().parents[2]
TABLER_DIR = BASE_DIR / "assets" / "icons" / "tabler"


def tabler_icon(name: str) -> QIcon:
    return QIcon(str(TABLER_DIR / f"{name}.svg"))


def awesome_icon(name: str, color: str = "#D4D4D8") -> QIcon:
    return qta.icon(name, color=QColor(color))


def app_icon(name: str, fallback: str = "fa6s.circle") -> QIcon:
    svg_path = TABLER_DIR / f"{name}.svg"

    if svg_path.exists():
        return QIcon(str(svg_path))

    return awesome_icon(fallback)