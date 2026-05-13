from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from app.config import AppConfig
from ui.components.app_button import AppButton
from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


class EditorToolbar(QWidget):
    load_video_requested = Signal()
    auto_transcribe_requested = Signal()
    translate_requested = Signal()
    generate_voice_requested = Signal()
    video_mp3_requested = Signal()
    export_video_requested = Signal()
    extract_audio_requested = Signal()
    export_dubbed_video_requested = Signal()
    import_khmer_srt_requested = Signal()
    settings_requested = Signal()

    def __init__(self, config: AppConfig):
        super().__init__()

        self.config = config
        self.selected_transcription_provider = config.transcription_provider
        self.selected_transcription_model = config.transcription_model
        self.selected_translation_provider = config.translation_provider
        self.selected_translation_model = config.translation_model

        self.setObjectName("toolbar")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        title = QLabel(f"{config.app_name} - AI Dubbing Studio")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("mainTitle")
        title.setFont(get_google_sans(size=16, weight="Bold"))

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        load_video_button = AppButton(
            text="Load Video",
            icon=app_icon("folder-open", "fa6s.folder-open", color="#ffffff"),
            variant="primary",
            button_size="sm",
            on_click=self.load_video_requested.emit,
        )

        extract_audio_button = AppButton(
            text="Extract Audio",
            icon=app_icon("waveform", "fa6s.wave-square", color="#ffffff"),
            variant="teal",
            button_size="sm",
            on_click=self.extract_audio_requested.emit,
        )

        auto_transcribe_button = AppButton(
            text="Auto Transcribe",
            icon=app_icon("microphone", "fa6s.microphone", color="#ffffff"),
            variant="danger",
            button_size="sm",
            on_click=self.auto_transcribe_requested.emit,
        )

        export_srt_button = AppButton(
            text="Export SRT",
            icon=app_icon("file-export", "fa6s.file-export", color="#ffffff"),
            variant="teal",
            button_size="sm",
            on_click=self.export_video_requested.emit,
        )

        import_khmer_srt_button = AppButton(
            text="Import Khmer SRT",
            icon=app_icon("file-import", "fa6s.file-import", color="#ffffff"),
            variant="secondary",
            button_size="sm",
            on_click=self.import_khmer_srt_requested.emit,
        )

        translate_button = AppButton(
            text="Translate",
            icon=app_icon("language", "fa6s.language", color="#ffffff"),
            variant="warning",
            button_size="sm",
            on_click=self.translate_requested.emit,
        )

        generate_voice_button = AppButton(
            text="Generate Voice",
            icon=app_icon("speakerphone", "fa6s.volume-high", color="#ffffff"),
            variant="success",
            button_size="sm",
            on_click=self.generate_voice_requested.emit,
        )

        video_mp3_button = AppButton(
            text="Vid → MP3",
            icon=app_icon("music", "fa6s.music", color="#ffffff"),
            variant="purple",
            button_size="sm",
            on_click=self.video_mp3_requested.emit,
        )

        export_dubbed_video_button = AppButton(
            text="Export Video",
            icon=app_icon("film", "fa6s.film", color="#ffffff"),
            variant="danger",
            button_size="sm",
            on_click=self.export_dubbed_video_requested.emit,
        )

        settings_button = AppButton(
            text="Settings",
            icon=app_icon("settings", "fa6s.gear", color="#ffffff"),
            variant="dark",
            button_size="sm",
            on_click=self.settings_requested.emit,
        )

        button_row.addWidget(load_video_button)
        button_row.addWidget(extract_audio_button)
        button_row.addWidget(auto_transcribe_button)
        button_row.addWidget(export_srt_button)
        button_row.addWidget(import_khmer_srt_button)
        button_row.addWidget(translate_button)
        button_row.addWidget(generate_voice_button)
        button_row.addWidget(video_mp3_button)
        button_row.addWidget(export_dubbed_video_button)
        button_row.addStretch()
        button_row.addWidget(settings_button)

        root.addWidget(title)
        root.addLayout(button_row)
    
    # ── getters used by EditorLayout ─────────────────────────────────────────

    def get_selected_transcription_provider(self) -> str:
        return self.selected_transcription_provider

    def get_selected_transcription_model(self) -> str:
        return self.selected_transcription_model

    def get_selected_translation_provider(self) -> str:
        return self.selected_translation_provider

    def get_selected_translation_model(self) -> str:
        return self.selected_translation_model

    # ── setters called after Settings dialog is accepted ─────────────────────

    def apply_settings(
        self,
        transcription_provider: str,
        transcription_model: str,
        translation_provider: str,
        translation_model: str,
    ) -> None:
        self.selected_transcription_provider = transcription_provider
        self.selected_transcription_model = transcription_model
        self.selected_translation_provider = translation_provider
        self.selected_translation_model = translation_model
