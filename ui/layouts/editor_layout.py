from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget
from PySide6.QtCore import QThread, Slot
from PySide6.QtWidgets import QMessageBox

## Import workers
from workers.transcription_worker import TranscriptionWorker
from workers.translation_worker import TranslationWorker

## Import app components
from app.config import AppConfig
from app.logger import get_logger
from app.state import AppState
from ui.components.editor_toolbar import EditorToolbar
from ui.components.status_bar_panel import StatusBarPanel
from ui.components.transcript_table_view import TranscriptTableView
from ui.components.timeline_editor import TimelineEditor
from ui.components.video_effects_panel import VideoEffectsPanel
from ui.components.video_preview_panel import VideoPreviewPanel

logger = get_logger(__name__)

class EditorLayout(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()

        self.state = AppState()
        self.config = config

        self.running_threads = []

        self.setObjectName("editorRoot")

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 6)
        root_layout.setSpacing(10)

        self.left_panel = self.build_left_panel()
        self.right_panel = self.build_right_panel()

        root_layout.addWidget(self.left_panel, 0)
        root_layout.addWidget(self.right_panel, 1)

        self.connect_signals()

    def build_left_panel(self):
        panel = QFrame()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(330)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.video_preview = VideoPreviewPanel()

        layout.addWidget(self.video_preview, 1)

        return panel

    def build_right_panel(self):
        panel = QFrame()
        panel.setObjectName("rightPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.toolbar = EditorToolbar(self.config)
        self.transcript_table = TranscriptTableView()
        self.transcript_table.hide()
        self.timeline_editor = TimelineEditor()
        self.effects_panel = VideoEffectsPanel()
        self.status_bar = StatusBarPanel()

        layout.addWidget(self.toolbar)
        layout.addWidget(self.transcript_table, 2)
        layout.addWidget(self.timeline_editor, 2)
        layout.addWidget(self.effects_panel)
        layout.addWidget(self.status_bar)

        return panel

    def connect_signals(self):
        self.toolbar.load_video_requested.connect(self.select_video)
        self.toolbar.auto_transcribe_requested.connect(self.auto_transcribe)
        self.toolbar.translate_requested.connect(self.translate_to_khmer)

        self.state.video_changed.connect(self.on_video_changed)
        self.state.transcript_changed.connect(self.on_transcript_changed)
        self.state.translation_changed.connect(self.on_segments_edited)

        self.transcript_table.segments_edited.connect(self.on_segments_edited)

        self.toolbar.translate_requested.connect(self.translate_to_khmer)

    def select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video",
            str(Path.home() / "Desktop"),
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
        )

        if not file_path:
            logger.info("Video selection cancelled.")
            return

        video_path = Path(file_path)

        if not video_path.exists():
            logger.warning("Selected video does not exist: %s", video_path)
            return

        logger.info("Selected video: %s", video_path)

        self.state.set_video(video_path)

    def on_video_changed(self, project):
        logger.info("Current project video: %s", project.video_path)

        self.video_preview.set_video(project.video_path)

    # def import_srt(self):
    #     file_path, _ = QFileDialog.getOpenFileName(
    #         self,
    #         "Import SRT Subtitle",
    #         str(Path.home() / "Desktop"),
    #         "Subtitle Files (*.srt);;All Files (*)",
    #     )

    #     if not file_path:
    #         logger.info("SRT import cancelled.")
    #         return

    #     srt_path = Path(file_path)

    #     if not srt_path.exists():
    #         logger.warning("Selected SRT does not exist: %s", srt_path)
    #         return

    #     try:
    #         segments = self.srt_service.parse(srt_path)
    #         print("SRT SEGMENTS:", len(segments))
    #         for segment in segments[:3]:
    #             print(segment)
    #     except Exception:
    #         logger.exception("Failed to parse SRT: %s", srt_path)
    #         return

    #     logger.info("Imported SRT: %s | segments=%s", srt_path, len(segments))

    #     self.state.set_subtitles(segments)

    ## Auto transcribe handler
    def auto_transcribe(self):
        video_path = self.state.get_video_path()

        if video_path is None:
            QMessageBox.warning(self, "No Video", "Please load a video first.")
            return

        selected_provider = self.toolbar.get_selected_transcription_provider()
        selected_model = self.toolbar.get_selected_transcription_model()

        logger.info(
            "Starting transcription for video=%s model=%s",
            video_path,
            selected_model,
        )

        self.status_bar.set_progress(0, "Preparing transcription...")

        thread = QThread(self)
        worker = TranscriptionWorker(
            config=self.config,
            video_path=video_path,
            provider=selected_provider,
            model=selected_model,
            language=self.config.transcription_language,
        )

        worker.moveToThread(thread)

        thread.worker = worker
        self.running_threads.append(thread)

        thread.started.connect(worker.run)

        worker.progress_changed.connect(self.on_transcription_progress)
        worker.finished.connect(self.on_transcription_finished)
        worker.failed.connect(self.on_transcription_failed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)

        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot(int, str)
    def on_transcription_progress(self, value: int, message: str):
        logger.info("Transcription progress %s%%: %s", value, message)
        self.status_bar.set_progress(value, message)


    @Slot(object)
    def on_transcription_finished(self, segments):
        logger.info("Transcription completed: %s segment(s)", len(segments))

        self.state.set_transcript(segments)

        self.status_bar.set_progress(
            100,
            f"Transcript ready: {len(segments)} segments. Click Translate Khmer.",
        )

        QMessageBox.information(
            self,
            "Transcription Complete",
            f"Generated {len(segments)} transcript segments.\n\nNext step: click Translate Khmer.",
        )


    @Slot(str)
    def on_transcription_failed(self, message: str):
        logger.error("Transcription failed: %s", message)

        self.status_bar.clear_progress()
        self.status_bar.set_status("Transcription failed")

        QMessageBox.critical(
            self,
            "Transcription Failed",
            message,
        )

    def cleanup_thread(self, thread: QThread):
        if thread in self.running_threads:
            self.running_threads.remove(thread)

        logger.info("Transcription thread cleaned up.")

    def on_transcript_changed(self, segments):
        logger.info("Transcript stored with %s segment(s).", len(segments))

        # Keep table hidden until Khmer translation is ready.
        self.transcript_table.hide()

    ## Translating to Khmer handler
    def on_segments_edited(self, segments):
        logger.info("Khmer translation ready with %s segment(s).", len(segments))

        self.transcript_table.set_segments(segments)
        self.transcript_table.show()

        self.status_bar.set_progress(
            100,
            f"Khmer translation ready: {len(segments)} segments.",
        )


    ## Translating to Khmer handler
    def translate_to_khmer(self):
        if not self.state.has_transcript:
            QMessageBox.warning(
                self,
                "No Transcript",
                "Please run Auto Transcribe first.",
            )
            return

        provider = self.toolbar.get_selected_translation_provider()
        model = self.toolbar.get_selected_translation_model()

        logger.info(
            "Starting Khmer translation provider=%s model=%s segments=%s",
            provider,
            model,
            len(self.state.segments),
        )

        self.status_bar.set_progress(0, "Preparing Khmer translation...")

        thread = QThread(self)
        worker = TranslationWorker(
            config=self.config,
            segments=self.state.segments,
            provider=provider,
            model=model,
            source_language=self.config.translation_source_language,
            target_language=self.config.translation_target_language,
        )

        worker.moveToThread(thread)

        thread.worker = worker
        self.running_threads.append(thread)

        thread.started.connect(worker.run)

        worker.progress_changed.connect(self.on_translation_progress)
        worker.finished.connect(self.on_translation_finished)
        worker.failed.connect(self.on_translation_failed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)

        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot(int, str)
    def on_translation_progress(self, value: int, message: str):
        logger.info("Translation progress %s%%: %s", value, message)
        self.status_bar.set_progress(value, message)


    @Slot(object)
    def on_translation_finished(self, segments):
        logger.info("Khmer translation completed: %s segment(s)", len(segments))

        self.state.set_translation(segments)

        self.transcript_table.set_segments(segments)
        self.transcript_table.show()

        self.status_bar.set_progress(
            100,
            f"Khmer translation complete: {len(segments)} segments",
        )

        QMessageBox.information(
            self,
            "Translation Complete",
            f"Translated {len(segments)} segments to Khmer.",
        )


    @Slot(str)
    def on_translation_failed(self, message: str):
        logger.error("Translation failed: %s", message)

        self.status_bar.clear_progress()
        self.status_bar.set_status("Translation failed")

        QMessageBox.critical(
            self,
            "Translation Failed",
            message,
        )