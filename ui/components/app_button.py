from typing import Callable, Optional, TypedDict

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QSizePolicy

class VariantConfig(TypedDict):
    bg: str
    hover: str
    pressed: str
    text: str
    border: str


class SizeConfig(TypedDict):
    height: int
    font: int
    padding: str
    radius: int


class AppButton(QPushButton):
    VARIANTS: dict[str, VariantConfig] = {
        "primary": {
            "bg": "#2563eb",
            "hover": "#1d4ed8",
            "pressed": "#1e40af",
            "text": "#ffffff",
            "border": "#2563eb",
        },
        "secondary": {
            "bg": "#e5e7eb",
            "hover": "#d1d5db",
            "pressed": "#9ca3af",
            "text": "#111827",
            "border": "#e5e7eb",
        },
        "danger": {
            "bg": "#dc2626",
            "hover": "#b91c1c",
            "pressed": "#991b1b",
            "text": "#ffffff",
            "border": "#dc2626",
        },
        "success": {
            "bg": "#16a34a",
            "hover": "#15803d",
            "pressed": "#166534",
            "text": "#ffffff",
            "border": "#16a34a",
        },
        "ghost": {
            "bg": "transparent",
            "hover": "#f3f4f6",
            "pressed": "#e5e7eb",
            "text": "#111827",
            "border": "transparent",
        },
        "outline": {
            "bg": "transparent",
            "hover": "#f3f4f6",
            "pressed": "#e5e7eb",
            "text": "#111827",
            "border": "#d1d5db",
        },
        "warning": {
            "bg": "#f97316",
            "hover": "#ea580c",
            "pressed": "#c2410c",
            "text": "#ffffff",
            "border": "#f97316",
        },
        "purple": {
            "bg": "#8e44ad",
            "hover": "#7d3c98",
            "pressed": "#6c3483",
            "text": "#ffffff",
            "border": "#8e44ad",
        },
        "teal": {
            "bg": "#16a085",
            "hover": "#138d75",
            "pressed": "#117a65",
            "text": "#ffffff",
            "border": "#16a085",
        },
        "dark": {
            "bg": "#374151",
            "hover": "#1f2937",
            "pressed": "#111827",
            "text": "#ffffff",
            "border": "#374151",
        },
    }

    SIZES: dict[str, SizeConfig] = {
        "sm": {
            "height": 32,
            "font": 12,
            "padding": "6px 12px",
            "radius": 6,
        },
        "md": {
            "height": 40,
            "font": 14,
            "padding": "8px 16px",
            "radius": 8,
        },
        "lg": {
            "height": 48,
            "font": 16,
            "padding": "10px 20px",
            "radius": 10,
        },
    }

    def __init__(
        self,
        text: str = "Button",
        variant: str = "primary",
        button_size: str = "md",
        full_width: bool = False,
        disabled: bool = False,
        loading: bool = False,
        icon: Optional[QIcon] = None,
        icon_size: int = 16,
        on_click: Optional[Callable[[], None]] = None,
    ):
        super().__init__(text)

        self.original_text = text
        self.variant_name = variant
        self.button_size = button_size
        self.full_width = full_width
        self.loading = loading

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if icon is not None:
            self.setIcon(icon)
            self.setIconSize(QSize(icon_size, icon_size))

        if on_click is not None:
            self.clicked.connect(on_click)

        self.setDisabled(disabled or loading)

        self.apply_size()
        self.apply_style()
        self.apply_loading()

    def apply_size(self):
        size_config = self.SIZES.get(self.button_size, self.SIZES["md"])

        self.setFixedHeight(size_config["height"])

        if self.full_width:
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
        else:
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def apply_style(self):
        variant_config = self.VARIANTS.get(
            self.variant_name,
            self.VARIANTS["primary"],
        )

        size_config = self.SIZES.get(
            self.button_size,
            self.SIZES["md"],
        )

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {variant_config["bg"]};
                color: {variant_config["text"]};
                border: 1px solid {variant_config["border"]};
                border-radius: {size_config["radius"]}px;
                font-size: {size_config["font"]}px;
                font-weight: 600;
                padding: {size_config["padding"]};
            }}

            QPushButton:hover {{
                background-color: {variant_config["hover"]};
            }}

            QPushButton:pressed {{
                background-color: {variant_config["pressed"]};
            }}

            QPushButton:disabled {{
                background-color: #e5e7eb;
                color: #9ca3af;
                border: 1px solid #e5e7eb;
            }}
        """)

    def apply_loading(self):
        if self.loading:
            self.setText("Loading...")
        else:
            self.setText(self.original_text)

    def set_loading(self, loading: bool):
        self.loading = loading
        self.setDisabled(loading)
        self.apply_loading()