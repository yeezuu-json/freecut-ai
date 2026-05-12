from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.components.app_button import AppButton
from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


class EffectTitle(QWidget):
    def __init__(
        self,
        text: str,
        icon_name: str,
        fallback: str,
        color: str = "#374151",
    ):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        icon = QLabel()
        icon.setPixmap(
            app_icon(
                icon_name,
                fallback=fallback,
                color=color,
                size=14,
            ).pixmap(QSize(14, 14))
        )

        label = QLabel(text)
        label.setObjectName("effectTitle")
        label.setFont(get_google_sans(size=9, weight="Bold"))

        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch()


class SmallLabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text)

        self.setObjectName("smallLabel")
        self.setFont(get_google_sans(size=8, weight="Medium"))


class NumberInput(QSpinBox):
    def __init__(
        self,
        value: int = 0,
        minimum: int = 0,
        maximum: int = 9999,
        width: int = 58,
    ):
        super().__init__()

        self.setObjectName("numberInput")
        self.setRange(minimum, maximum)
        self.setValue(value)
        self.setFixedWidth(width)
        self.setFixedHeight(28)
        self.setFont(get_google_sans(size=9, weight="Medium"))
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)


class VideoEffectsPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("effectsPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title_icon = QLabel()
        title_icon.setPixmap(
            app_icon(
                "sparkles",
                fallback="fa6s.sparkles",
                color="#f59e0b",
                size=14,
            ).pixmap(QSize(14, 14))
        )

        title = QLabel("Video Effects")
        title.setObjectName("sectionTitle")
        title.setFont(get_google_sans(size=10, weight="Bold"))

        header.addWidget(title_icon)
        header.addWidget(title)
        header.addStretch()

        body = QHBoxLayout()
        body.setSpacing(10)

        blur_panel = self.build_blur_panel()
        text_panel = self.build_text_panel()
        logo_panel = self.build_logo_panel()

        apply_effects = AppButton(
            text="Apply Effect",
            icon=app_icon("sparkles", fallback="fa6s.sparkles", color="#ffffff"),
            variant="purple",
            button_size="md",
        )
        apply_effects.setFixedWidth(145)

        body.addWidget(blur_panel, 1)
        body.addWidget(text_panel, 1)
        body.addWidget(logo_panel, 1)
        body.addWidget(apply_effects)

        layout.addLayout(header)
        layout.addLayout(body)

    def build_blur_panel(self):
        panel = QFrame()
        panel.setObjectName("effectGroup")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)

        checkbox = QCheckBox()
        checkbox.setObjectName("cleanCheckBox")

        title = EffectTitle(
            text="Blur",
            icon_name="blur",
            fallback="fa6s.circle-half-stroke",
            color="#64748b",
        )

        top.addWidget(checkbox)
        top.addWidget(title, 1)

        intensity_row = QHBoxLayout()
        intensity_row.setSpacing(8)

        intensity_label = SmallLabel("Intensity")

        intensity = QSlider(Qt.Orientation.Horizontal)
        intensity.setObjectName("compactSlider")
        intensity.setRange(0, 100)
        intensity.setValue(10)

        intensity_value = QLabel("10")
        intensity_value.setObjectName("valueText")
        intensity_value.setFixedWidth(24)
        intensity_value.setFont(get_google_sans(size=9, weight="Bold"))

        intensity.valueChanged.connect(lambda value: intensity_value.setText(str(value)))

        intensity_row.addWidget(intensity_label)
        intensity_row.addWidget(intensity, 1)
        intensity_row.addWidget(intensity_value)

        position_row = QHBoxLayout()
        position_row.setSpacing(6)

        x_input = NumberInput(50)
        y_input = NumberInput(50)
        w_input = NumberInput(200)
        h_input = NumberInput(200)

        position_row.addWidget(SmallLabel("X"))
        position_row.addWidget(x_input)
        position_row.addWidget(SmallLabel("Y"))
        position_row.addWidget(y_input)
        position_row.addWidget(SmallLabel("W"))
        position_row.addWidget(w_input)
        position_row.addWidget(SmallLabel("H"))
        position_row.addWidget(h_input)
        position_row.addStretch()

        layout.addLayout(top)
        layout.addLayout(intensity_row)
        layout.addLayout(position_row)

        return panel

    def build_text_panel(self):
        panel = QFrame()
        panel.setObjectName("effectGroup")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)

        checkbox = QCheckBox()
        checkbox.setObjectName("cleanCheckBox")

        title = EffectTitle(
            text="Text Overlay",
            icon_name="text-caption",
            fallback="fa6s.font",
            color="#64748b",
        )

        top.addWidget(checkbox)
        top.addWidget(title, 1)

        text_input = QLineEdit()
        text_input.setObjectName("cleanInput")
        text_input.setPlaceholderText("Enter text...")
        text_input.setFixedHeight(32)
        text_input.setFont(get_google_sans(size=9, weight="Regular"))

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)

        font_label = QLabel("Khmer OS System")
        font_label.setObjectName("pillText")
        font_label.setFont(get_google_sans(size=8, weight="Medium"))

        size_input = NumberInput(40, minimum=8, maximum=200, width=50)

        meta_row.addWidget(SmallLabel("Font"))
        meta_row.addWidget(font_label)
        meta_row.addSpacing(8)
        meta_row.addWidget(SmallLabel("Size"))
        meta_row.addWidget(size_input)
        meta_row.addStretch()

        position_row = QHBoxLayout()
        position_row.setSpacing(6)

        x_input = NumberInput(50)
        y_input = NumberInput(50)

        position_row.addWidget(SmallLabel("X"))
        position_row.addWidget(x_input)
        position_row.addWidget(SmallLabel("Y"))
        position_row.addWidget(y_input)
        position_row.addStretch()

        layout.addLayout(top)
        layout.addWidget(text_input)
        layout.addLayout(meta_row)
        layout.addLayout(position_row)

        return panel

    def build_logo_panel(self):
        panel = QFrame()
        panel.setObjectName("effectGroup")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)

        checkbox = QCheckBox()
        checkbox.setObjectName("cleanCheckBox")

        title = EffectTitle(
            text="Logo",
            icon_name="photo",
            fallback="fa6s.image",
            color="#64748b",
        )

        top.addWidget(checkbox)
        top.addWidget(title, 1)

        browse = AppButton(
            text="Browse Logo",
            icon=app_icon("folder-open", fallback="fa6s.folder-open", color="#ffffff"),
            variant="purple",
            button_size="sm",
        )
        browse.setFixedWidth(135)

        position_row = QHBoxLayout()
        position_row.setSpacing(6)

        x_input = NumberInput(10)
        y_input = NumberInput(10)
        scale_input = NumberInput(100, minimum=1, maximum=500, width=60)

        position_row.addWidget(SmallLabel("X"))
        position_row.addWidget(x_input)
        position_row.addWidget(SmallLabel("Y"))
        position_row.addWidget(y_input)
        position_row.addWidget(SmallLabel("Scale"))
        position_row.addWidget(scale_input)
        position_row.addWidget(SmallLabel("%"))
        position_row.addStretch()

        layout.addLayout(top)
        layout.addWidget(browse)
        layout.addLayout(position_row)

        return panel