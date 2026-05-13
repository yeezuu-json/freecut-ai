from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import (
    QColor, QCursor, QFontMetrics, QLinearGradient,
    QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import QWidget

from models.timeline_item import TimelineItem
from utils.font_manager import get_google_sans


# (top-color, bottom-color) per item type
_CLIP_COLORS: dict[str, tuple[str, str]] = {
    "video":        ("#3b82f6", "#1d4ed8"),
    "raw_audio":    ("#f59e0b", "#b45309"),
    "background":   ("#10b981", "#065f46"),
    "vocal":        ("#a78bfa", "#5b21b6"),
    "dubbed_voice": ("#f472b6", "#9d174d"),
}


class TimelineClipWidget(QWidget):
    clip_clicked  = Signal(object, int)  # TimelineItem, frame_at_click
    drag_adjusted = Signal(str, int)     # item_id, delta_frames

    _DRAG_THRESHOLD = 4  # px before treating movement as a drag

    def __init__(self, item: TimelineItem, ppf: float = 0.6):
        """ppf = pixels per frame"""
        super().__init__()

        self.item = item
        self.ppf  = ppf

        self._drag_origin_x: int | None = None
        self._is_dragging   = False
        self._hovered       = False

        top, bot = _CLIP_COLORS.get(item.type, ("#6b7280", "#374151"))
        self._color_top = QColor(top)
        self._color_bot = QColor(bot)

        self.setFixedHeight(28)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._font = get_google_sans(size=9, weight="Bold")

    # ----------------------------------------------------------------- paint

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r      = self.rect().adjusted(0, 0, -1, -1)
        radius = 5.0

        top = QColor(self._color_top)
        bot = QColor(self._color_bot)
        if self._hovered:
            top = top.lighter(125)
            bot = bot.lighter(115)

        # gradient fill
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0, top)
        grad.setColorAt(1, bot)

        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        painter.fillPath(path, grad)

        # clip painter to the rounded path for all decoration
        painter.setClipPath(path)

        # type-specific decoration
        item_type = self.item.type
        if item_type == "video":
            self._draw_filmstrip(painter, r)
        elif item_type in ("raw_audio", "background", "vocal", "dubbed_voice"):
            self._draw_waveform(painter, r)

        # top shine
        painter.setClipping(False)
        shine = QLinearGradient(r.topLeft(), QPoint(r.left(), r.top() + r.height() // 3))
        shine.setColorAt(0, QColor(255, 255, 255, 35))
        shine.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillPath(path, shine)

        # border
        pen = QPen(QColor(255, 255, 255, 50))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

        # label (always on top)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(self._font)
        text_rect = r.adjusted(8, 0, -4, 0)
        fm   = QFontMetrics(self._font)
        text = fm.elidedText(self.item.label, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )

    # ------------------------------------------------------ clip decorations

    def _draw_filmstrip(self, painter: QPainter, r: QRect):
        """Draw filmstrip sprocket holes along top and bottom edges."""
        painter.setPen(Qt.PenStyle.NoPen)
        hole_color = QColor(0, 0, 0, 70)
        painter.setBrush(hole_color)

        hole_w, hole_h = 5, 4
        spacing = 10
        y_top = r.top() + 2
        y_bot = r.bottom() - hole_h - 2

        x = r.left() + 6
        while x + hole_w < r.right() - 4:
            painter.drawRoundedRect(x, y_top, hole_w, hole_h, 1, 1)
            painter.drawRoundedRect(x, y_bot, hole_w, hole_h, 1, 1)
            x += hole_w + spacing

        # Vertical frame dividers
        divider_color = QColor(0, 0, 0, 30)
        painter.setPen(QPen(divider_color, 1))
        frame_w = 28
        x = r.left() + frame_w
        while x < r.right():
            painter.drawLine(x, r.top() + 8, x, r.bottom() - 8)
            x += frame_w

    def _draw_waveform(self, painter: QPainter, r: QRect):
        """Draw a pseudo-random waveform centered vertically in the clip."""
        painter.setPen(Qt.PenStyle.NoPen)
        bar_color = QColor(255, 255, 255, 55)
        painter.setBrush(bar_color)

        bar_w  = 2
        gap    = 2
        step   = bar_w + gap
        center = r.top() + r.height() // 2
        max_h  = r.height() // 2 - 3

        # Deterministic "random" heights seeded from clip id
        seed = abs(hash(self.item.id)) & 0xFFFFFFFF

        x = r.left() + 4
        while x + bar_w <= r.right() - 4:
            seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
            h = 2 + int((seed & 0xFF) / 255.0 * max_h)
            painter.drawRoundedRect(x, center - h, bar_w, h * 2, 1, 1)
            x += step

    # --------------------------------------------------------------- hover

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    # --------------------------------------------------------------- mouse

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin_x = event.pos().x()
            self._is_dragging   = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin_x is not None:
            delta_px = event.pos().x() - self._drag_origin_x
            if abs(delta_px) >= self._DRAG_THRESHOLD:
                self._is_dragging = True
                delta_frames = int(delta_px / max(self.ppf, 0.01))
                if delta_frames != 0:
                    self.drag_adjusted.emit(self.item.id, delta_frames)
                    self._drag_origin_x = event.pos().x()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                # Seek to the frame at the click position inside the clip,
                # not just the clip's start frame.
                frame = self.item.from_frame + int(
                    event.pos().x() / max(self.ppf, 0.01)
                )
                self.clip_clicked.emit(self.item, frame)
            self._drag_origin_x = None
            self._is_dragging   = False
        super().mouseReleaseEvent(event)

    # ---------------------------------------------------------------- public

    def set_ppf(self, ppf: float):
        self.ppf = ppf
