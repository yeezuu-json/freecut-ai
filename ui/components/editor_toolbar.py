from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from app.config import AppConfig
from ui.components.app_button import AppButton
from ui.components.app_select import AppSelect
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

        self.model_select = AppSelect(
            items=[model.label for model in config.transcription_models],
            value=self.get_model_label(self.selected_transcription_model),
            width=210,
            height=32,
            on_change=self.on_model_changed,
        )

        auto_transcribe_button = AppButton(
            text="Auto Transcribe",
            icon=app_icon("microphone", "fa6s.microphone", color="#ffffff"),
            variant="danger",
            button_size="sm",
            on_click=self.auto_transcribe_requested.emit,
        )

        video_mp3_button = AppButton(
            text="Vid -> MP3",
            icon=app_icon("music", "fa6s.music", color="#ffffff"),
            variant="purple",
            button_size="sm",
            on_click=self.video_mp3_requested.emit,
        )

        extract_audio_button = AppButton(
            text="Ext Audio",
            icon=app_icon("waveform", "fa6s.wave-square", color="#ffffff"),
            variant="teal",
            button_size="sm",
            on_click=self.extract_audio_requested.emit,
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

        export_srt_button = AppButton(
            text="Export SRT",
            icon=app_icon("file-export", "fa6s.file-export", color="#ffffff"),
            variant="teal",
            button_size="sm",
            on_click=self.export_video_requested.emit,
        )

        translation_model_select = AppSelect(
            items=[model.label for model in config.translation_models],
            value=self.get_translation_model_label(config.translation_model),
            width=230,
            on_change=self.on_translation_model_changed,
        )

        button_row.addWidget(load_video_button)
        button_row.addWidget(extract_audio_button)
        button_row.addWidget(self.model_select)
        button_row.addWidget(auto_transcribe_button)
        button_row.addWidget(translation_model_select)
        button_row.addWidget(translate_button)
        button_row.addWidget(generate_voice_button)
        button_row.addWidget(video_mp3_button)
        # button_row.addWidget(export_srt_button)
        button_row.addStretch()

        root.addWidget(title)
        root.addLayout(button_row)
    
    ## Transcription model select
    def on_model_changed(self, label: str):
        for model in self.config.transcription_models:
            if model.label == label:
                self.selected_transcription_provider = model.provider
                self.selected_transcription_model = model.value
                return

    def get_selected_transcription_provider(self) -> str:
        return self.selected_transcription_provider

    def get_selected_transcription_model(self) -> str:
        return self.selected_transcription_model

    def get_model_label(self, value: str) -> str:
        for model in self.config.transcription_models:
            if model.value == value:
                return model.label
        return "Default Model"

    ## Translation model select
    def get_translation_model_label(self, value: str) -> str:
        for model in self.config.translation_models:
            if model.value == value:
                return model.label

        if self.config.translation_models:
            return self.config.translation_models[0].label

        return "Default Translation"

    def get_selected_translation_provider(self) -> str:
        return self.selected_translation_provider

    def get_selected_translation_model(self) -> str:
        return self.selected_translation_model

    def on_translation_model_changed(self, label: str):
        for model in self.config.translation_models:
            if model.label == label:
                self.selected_translation_provider = model.provider
                self.selected_translation_model = model.value
                return
