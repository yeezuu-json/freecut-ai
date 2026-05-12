from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QIcon, QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


BASE_DIR = Path(__file__).resolve().parents[2]
TABLER_DIR = BASE_DIR / "assets" / "icons" / "tabler"


def colored_svg_icon(svg_path: Path, color: str = "#ffffff", size: int = 18) -> QIcon:
    svg_content = svg_path.read_text(encoding="utf-8")

    # Tabler usually uses currentColor
    svg_content = svg_content.replace("currentColor", color)

    # Extra safety for SVGs that use black directly
    svg_content = svg_content.replace('stroke="black"', f'stroke="{color}"')
    svg_content = svg_content.replace('stroke="#000"', f'stroke="{color}"')
    svg_content = svg_content.replace('stroke="#000000"', f'stroke="{color}"')

    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))

    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(QColor("transparent"))

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


def tabler_icon(name: str, color: str = "#ffffff", size: int = 18) -> QIcon:
    svg_path = TABLER_DIR / f"{name}.svg"

    if not svg_path.exists():
        return QIcon()

    return colored_svg_icon(svg_path, color=color, size=size)


def awesome_icon(name: str, color: str = "#ffffff") -> QIcon:
    return qta.icon(name, color=QColor(color))


def app_icon(
    name: str,
    fallback: str = "fa6s.circle",
    color: str = "#ffffff",
    size: int = 18,
) -> QIcon:
    svg_path = TABLER_DIR / f"{name}.svg"

    if svg_path.exists():
        return colored_svg_icon(svg_path, color=color, size=size)

    return awesome_icon(fallback, color=color)