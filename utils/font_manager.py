from pathlib import Path
from typing import Optional

from PySide6.QtGui import QFontDatabase, QFont

from app.logger import get_logger


logger = get_logger(__name__)


class FontManager:
    def __init__(self):
        self.loaded_fonts: dict[str, str] = {}
        self._fonts_loaded = False

    def load_fonts(self, fonts_dir: Optional[Path] = None) -> None:
        if self._fonts_loaded:
            logger.debug("Fonts already loaded. Skipping.")
            return

        if fonts_dir is None:
            logger.warning("No fonts directory provided.")
            self._fonts_loaded = True
            return

        if not fonts_dir.exists():
            logger.warning("Fonts directory not found: %s", fonts_dir)
            self._fonts_loaded = True
            return

        font_extensions = (".ttf", ".otf")
        loaded_count = 0

        for font_path in fonts_dir.rglob("*"):
            if font_path.suffix.lower() not in font_extensions:
                continue

            font_id = QFontDatabase.addApplicationFont(str(font_path))

            if font_id == -1:
                logger.warning("Failed to load font: %s", font_path)
                continue

            families = QFontDatabase.applicationFontFamilies(font_id)

            for family in families:
                if family not in self.loaded_fonts:
                    logger.info("Loaded font family: %s", family)

                self.loaded_fonts[family] = str(font_path)

            loaded_count += 1

        logger.info("Loaded %s font file(s).", loaded_count)

        self._fonts_loaded = True

    def get_font(
        self,
        family: str = "Google Sans",
        size: int = 10,
        weight: QFont.Weight = QFont.Weight.Normal,
        italic: bool = False,
    ) -> QFont:
        font = QFont(family, size)
        font.setWeight(weight)
        font.setItalic(italic)
        return font

    def get_google_sans(
        self,
        size: int = 10,
        weight: str = "Regular",
        italic: bool = False,
    ) -> QFont:
        weight_map = {
            "Regular": QFont.Weight.Normal,
            "Medium": QFont.Weight.Medium,
            "SemiBold": QFont.Weight.DemiBold,
            "Bold": QFont.Weight.Bold,
        }

        qfont_weight = weight_map.get(weight, QFont.Weight.Normal)
        return self.get_font("Google Sans", size, qfont_weight, italic)

    def list_loaded_fonts(self) -> dict[str, str]:
        return self.loaded_fonts.copy()

    def is_font_available(self, family: str) -> bool:
        return family in QFontDatabase.families()


_font_manager: FontManager | None = None


def get_font_manager() -> FontManager:
    global _font_manager

    if _font_manager is None:
        _font_manager = FontManager()

    return _font_manager


def load_fonts(fonts_dir: Optional[Path] = None) -> None:
    get_font_manager().load_fonts(fonts_dir)


def get_google_sans(
    size: int = 10,
    weight: str = "Regular",
    italic: bool = False,
) -> QFont:
    return get_font_manager().get_google_sans(size, weight, italic)