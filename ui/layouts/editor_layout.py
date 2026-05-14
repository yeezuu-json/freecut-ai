from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget, QMessageBox
from PySide6.QtCore import QThread, QUrl, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

## Import workers
from workers.audio_extraction_worker import AudioExtractionWorker
from workers.transcription_worker import TranscriptionWorker
from workers.translation_worker import TranslationWorker
from workers.tts_worker import TtsWorker
from workers.video_to_mp3_worker import VideoToMp3Worker

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

## Import services
from services.audio_service import AudioService
from services.timeline_builder_service import TimelineBuilderService
from services.timeline_cache_service import TimelineCacheService
from stores.timeline_store import TimelineStore
from workers.capcut_export_worker import CapCutExportWorker
from services.capcut_app_service import CapCutAppService
from services.capcut_export_service import CapCutExportService

logger = get_logger(__name__)

class EditorLayout(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()

        self.state = AppState()
        self.config = config

        self.running_threads = []

        self.setObjectName("editorRoot")

        self.timeline_cache_service = TimelineCacheService()
        self.timeline_builder_service = TimelineBuilderService()
        self.timeline_store = TimelineStore()
        self.current_timeline_cache = None
        self.audio_service = AudioService()
        self.capcut_app_service = CapCutAppService()
        self.capcut_export_service = CapCutExportService()

        # Stem audio players created after Demucs extraction.
        # Keyed by track_id → (QMediaPlayer, QAudioOutput)
        self._stem_players: dict[str, tuple[QMediaPlayer, QAudioOutput]] = {}

        # Position-driven player for per-segment TTS clips.
        self._dubbed_voice_player = None

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
        self.timeline_editor = TimelineEditor()
        # self.effects_panel = VideoEffectsPanel()
        self.status_bar = StatusBarPanel()

        layout.addWidget(self.toolbar)
        layout.addWidget(self.transcript_table, 2)
        layout.addWidget(self.timeline_editor, 2)
        # layout.addWidget(self.effects_panel)
        layout.addWidget(self.status_bar)

        return panel

    def connect_signals(self):
        self.toolbar.load_video_requested.connect(self.select_video)
        self.toolbar.auto_transcribe_requested.connect(self.auto_transcribe)
        self.toolbar.translate_requested.connect(self.translate_to_khmer)
        self.toolbar.extract_audio_requested.connect(self.extract_audio)
        self.toolbar.generate_voice_requested.connect(self.generate_voice)
        self.toolbar.video_mp3_requested.connect(self.export_video_to_mp3)
        self.toolbar.export_dubbed_video_requested.connect(self.export_dubbed_video)
        self.toolbar.import_khmer_srt_requested.connect(self.import_khmer_srt)
        self.toolbar.export_video_requested.connect(self.export_srt)
        self.toolbar.settings_requested.connect(self.show_settings)

        self.state.video_changed.connect(self.on_video_changed)
        self.state.transcript_changed.connect(self.on_transcript_changed)
        self.state.translation_changed.connect(self.on_translation_segments_loaded)

        self.transcript_table.segments_edited.connect(self.on_table_segments_edited)

        self.status_bar.export_capcut_requested.connect(self.export_to_capcut)

        # ── Timeline ↔ Video player bidirectional sync ──────────────────
        self.video_preview.player.positionChanged.connect(
            self.timeline_editor.set_playhead
        )
        self.video_preview.player.positionChanged.connect(
            self._sync_dubbed_voice_position
        )
        self.video_preview.player.playbackStateChanged.connect(
            self._sync_stem_playback
        )
        self.timeline_editor.seek_requested.connect(self._on_timeline_seek)
        self.timeline_editor.clip_clicked.connect(self._on_clip_clicked)
        self.timeline_editor.mute_toggled.connect(self._on_track_mute_toggled)
        self.timeline_editor.drag_adjusted.connect(self._on_clip_drag_adjusted)
        self.timeline_editor.voice_library_requested.connect(self._open_voice_library)

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

        cached = self.timeline_cache_service.load(project.video_path)

        _REQUIRED_ITEM_IDS = {"item_video", "item_raw_audio", "item_background", "item_vocal"}
        should_rebuild = cached is None or bool(
            _REQUIRED_ITEM_IDS - {item.id for item in cached.items}
        )

        if should_rebuild:
            duration_seconds = self.audio_service.get_duration_seconds(project.video_path)
            duration_ms = int(duration_seconds * 1000)

            self.current_timeline_cache = self.timeline_builder_service.build_from_video(
                video_path=project.video_path,
                duration_ms=duration_ms,
                fps=30.0,
            )
            self.timeline_cache_service.save(self.current_timeline_cache)
        else:
            self.current_timeline_cache = cached
            logger.info("Using existing timeline cache.")

        logger.info(
            "Timeline cache loaded: tracks=%s items=%s",
            len(self.current_timeline_cache.tracks),
            len(self.current_timeline_cache.items),
        )

        self.timeline_store.load_cache(self.current_timeline_cache)
        self.timeline_editor.set_timeline_store(
            self.timeline_store,
            self.current_timeline_cache.duration_ms,
        )

        # Offer to restore expensive AI results from a previous session.
        if not should_rebuild:
            self._maybe_offer_restore(self.current_timeline_cache)

    def _maybe_offer_restore(self, cache) -> None:
        """Show the restore dialog if any cached AI step has valid data."""
        from ui.components.restore_cache_dialog import CacheStatus, RestoreCacheDialog, inspect_cache

        status = inspect_cache(cache)
        has_anything = any([
            status.has_demucs,
            status.has_transcript,
            status.has_translation,
            status.has_tts,
        ])
        if not has_anything:
            return

        dialog = RestoreCacheDialog(cache=cache, status=status, parent=self)
        dialog.exec()

        if dialog.should_restore():
            self._restore_from_cache(cache, status)
        else:
            # User chose "Start Fresh" — clear AI data from cache but keep layout.
            cache.segments = []
            cache.vocals_path = None
            cache.background_path = None
            cache.raw_audio_path = None
            self.timeline_cache_service.save(cache)
            logger.info("Cache cleared by user (Start Fresh).")

    def _restore_from_cache(self, cache, status) -> None:
        """Rebuild in-memory state from the persisted cache."""
        from services.srt_service import SrtService  # noqa: F401 (unused here)

        segs = list(cache.segments) if cache.segments else []

        # ── Restore transcript / translation ──────────────────────────────────
        if status.has_translation:
            self.state.set_translation(segs)
            self.transcript_table.set_segments(segs)
            self.transcript_table.show()
            logger.info("Restored %d translated segment(s) from cache.", len(segs))
        elif status.has_transcript:
            self.state.set_transcript(segs)
            self.transcript_table.set_segments(segs)
            self.transcript_table.show()
            logger.info("Restored %d transcript segment(s) from cache.", len(segs))

        # ── Restore Demucs stem players ───────────────────────────────────────
        if status.has_demucs:
            from services.demucs_service import DemucsResult
            demucs_result = DemucsResult(
                vocals_path=Path(cache.vocals_path),
                background_path=Path(cache.background_path),
                raw_audio_path=Path(cache.raw_audio_path) if cache.raw_audio_path else Path(cache.vocals_path).parent / "raw.wav",
                model_used="htdemucs",
            )
            self._setup_stem_players(demucs_result)
            logger.info("Restored Demucs stem players from cache.")

        # ── Restore TTS dubbed voice player ───────────────────────────────────
        if status.has_tts:
            self._build_dubbed_player(segs)
            logger.info("Restored dubbed voice player (%d clips).", status.tts_count)

        # ── Rebuild timeline with tts segments ────────────────────────────────
        if status.has_tts and segs:
            self.timeline_builder_service.attach_tts_segments(cache, segs)
            self.timeline_cache_service.save(cache)
            self.timeline_store.load_cache(cache)
            self.timeline_editor.set_timeline_store(
                self.timeline_store, cache.duration_ms
            )

        # Status summary
        parts = []
        if status.has_demucs:    parts.append("Demucs ✓")
        if status.has_transcript: parts.append("Transcript ✓")
        if status.has_translation: parts.append("Translation ✓")
        if status.has_tts:        parts.append(f"TTS {status.tts_count}/{status.tts_total} ✓")
        self.status_bar.set_progress(100, "Restored: " + "  ".join(parts))

    # ── Timeline signal handlers ─────────────────────────────────────────

    @Slot(int)
    def _on_timeline_seek(self, frame: int):
        """Ruler click or playhead drag → seek the video player and all stems."""
        fps = self.timeline_store.fps if self.timeline_store else 30.0
        ms = int(frame / max(fps, 1.0) * 1000)
        self._seek_all(ms)

    @Slot(object, int)
    def _on_clip_clicked(self, item, frame: int):
        """Seek to the exact frame the user clicked on inside the clip."""
        fps = self.timeline_store.fps if self.timeline_store else 30.0
        ms  = int(frame / max(fps, 1.0) * 1000)
        self._seek_all(ms)
        logger.info("Clip clicked: %s → seek to %dms (frame %d)", item.label, ms, frame)

    @Slot(str, bool)
    def _on_track_mute_toggled(self, track_id: str, muted: bool) -> None:
        logger.info("Track mute toggled: track=%s muted=%s", track_id, muted)

        if track_id == "track_khmer_voice" and self._dubbed_voice_player is not None:
            self._dubbed_voice_player.set_muted(muted)
            if not muted:
                is_playing = (
                    self.video_preview.player.playbackState()
                    == QMediaPlayer.PlaybackState.PlayingState
                )
                if is_playing:
                    self._dubbed_voice_player.play()
                    self._dubbed_voice_player.on_position_changed(
                        self.video_preview.player.position()
                    )
        elif track_id in self._stem_players:
            _, output = self._stem_players[track_id]
            output.setMuted(muted)
            player, _ = self._stem_players[track_id]
            is_playing = (
                self.video_preview.player.playbackState()
                == QMediaPlayer.PlaybackState.PlayingState
            )
            if is_playing:
                if muted:
                    player.pause()
                else:
                    player.setPosition(self.video_preview.player.position())
                    player.play()
        elif track_id in ("track_video", "track_raw_audio"):
            self.video_preview.audio_output.setMuted(muted)

        # Persist mute state back into the cache.
        if self.current_timeline_cache:
            for track in self.current_timeline_cache.tracks:
                if track.id == track_id:
                    track.muted = muted
                    break

    @Slot(object)
    def _sync_stem_playback(self, state: QMediaPlayer.PlaybackState) -> None:
        """Mirror the main player's play/pause/stop on all stem players."""
        pos = self.video_preview.player.position()
        for player, output in self._stem_players.values():
            if state == QMediaPlayer.PlaybackState.PlayingState:
                if not output.isMuted():
                    player.setPosition(pos)
                    player.play()
            elif state == QMediaPlayer.PlaybackState.PausedState:
                player.pause()
            else:
                player.stop()

        # Sync the dubbed voice player.
        if self._dubbed_voice_player is not None:
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self._dubbed_voice_player.play()
                self._dubbed_voice_player.on_position_changed(pos)
            elif state == QMediaPlayer.PlaybackState.PausedState:
                self._dubbed_voice_player.pause()
            else:
                self._dubbed_voice_player.stop()

    @Slot(int)
    def _sync_dubbed_voice_position(self, pos_ms: int) -> None:
        """Feed playhead position into the dubbed voice player every tick."""
        if self._dubbed_voice_player is not None:
            self._dubbed_voice_player.on_position_changed(pos_ms)

    def _seek_all(self, ms: int) -> None:
        """Seek the main player AND all stem/dubbed players to the same position."""
        self.video_preview.player.setPosition(ms)
        for player, _ in self._stem_players.values():
            player.setPosition(ms)
        if self._dubbed_voice_player is not None:
            self._dubbed_voice_player.seek(ms)

    def _setup_stem_players(self, result) -> None:
        """Create (or recreate) QMediaPlayer instances for each Demucs stem."""
        stem_map = {
            "track_raw_audio": result.raw_audio_path,
            "track_background": result.background_path,
            "track_vocal":      result.vocals_path,
        }

        for track_id, path in stem_map.items():
            # Stop and discard any previous player for this stem.
            if track_id in self._stem_players:
                old_player, _ = self._stem_players.pop(track_id)
                old_player.stop()
                old_player.deleteLater()

            output = QAudioOutput(self)
            player = QMediaPlayer(self)
            player.setAudioOutput(output)
            player.setSource(QUrl.fromLocalFile(str(path)))

            # Apply the mute state already stored in the timeline cache.
            muted = True  # safe default
            if self.current_timeline_cache:
                for track in self.current_timeline_cache.tracks:
                    if track.id == track_id:
                        muted = track.muted
                        break
            output.setMuted(muted)

            self._stem_players[track_id] = (player, output)

        # Mute the main video player's built-in audio so only stems are heard.
        self.video_preview.audio_output.setMuted(True)
        logger.info("Stem players set up for %s", list(stem_map.keys()))

    @Slot(str, int)
    def _on_clip_drag_adjusted(self, item_id: str, delta_frames: int):
        logger.info("Clip drag: item=%s delta=%d frames", item_id, delta_frames)

    # ── Audio extraction (Demucs) ────────────────────────────────────────────

    def extract_audio(self) -> None:
        """Separate the loaded video's audio into vocal and background stems."""
        video_path = self.state.get_video_path()

        if video_path is None:
            QMessageBox.warning(self, "No Video", "Please load a video first.")
            return

        if self.current_timeline_cache is None:
            QMessageBox.warning(
                self,
                "No Timeline",
                "Load a video first so the timeline is initialised.",
            )
            return

        logger.info("Starting Demucs audio extraction for: %s", video_path)
        self.status_bar.set_progress(0, "Starting audio extraction…")

        thread = QThread(self)
        worker = AudioExtractionWorker(video_path=video_path)

        worker.moveToThread(thread)
        thread.worker = worker
        self.running_threads.append(thread)

        thread.started.connect(worker.run)

        worker.progress_changed.connect(self.on_extraction_progress)
        worker.finished.connect(self.on_extraction_finished)
        worker.failed.connect(self.on_extraction_failed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)

        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot(int, str)
    def on_extraction_progress(self, value: int, message: str) -> None:
        logger.info("Extraction %d%%: %s", value, message)
        self.status_bar.set_progress(value, message)

    @Slot(object)
    def on_extraction_finished(self, result) -> None:
        logger.info(
            "Extraction finished — vocals=%s background=%s",
            result.vocals_path,
            result.background_path,
        )
        self.status_bar.set_progress(100, "Audio extraction complete")

        if self.current_timeline_cache is None:
            return

        # Attach the real stem paths to the existing placeholder items.
        self.timeline_builder_service.attach_audio_sources(
            self.current_timeline_cache,
            raw_audio_path=result.raw_audio_path,
            vocals_path=result.vocals_path,
            background_path=result.background_path,
        )

        # Persist the updated cache.
        self.timeline_cache_service.save(self.current_timeline_cache)

        # Create stem players so each track can be independently muted.
        self._setup_stem_players(result)

        # Reload the timeline store so the new source_paths are visible.
        self.timeline_store.load_cache(self.current_timeline_cache)
        self.timeline_editor.set_timeline_store(
            self.timeline_store,
            self.current_timeline_cache.duration_ms,
        )

        QMessageBox.information(
            self,
            "Audio Extraction Complete",
            "Vocal and background stems have been separated and loaded into the timeline.",
        )

    @Slot(str)
    def on_extraction_failed(self, error: str) -> None:
        logger.error("Audio extraction failed: %s", error)
        self.status_bar.set_progress(0, "Audio extraction failed")
        QMessageBox.critical(self, "Audio Extraction Failed", error)

    # ── TTS – Generate Voice ─────────────────────────────────────────────────

    def generate_voice(self) -> None:
        """Run Edge TTS on every translated segment and load audio into the timeline."""
        segments = self.state.get_transcript()
        if not segments:
            QMessageBox.warning(self, "No Transcript", "Run Auto Transcribe first.")
            return

        has_translation = any(s.khmer_text.strip() for s in segments)
        if not has_translation:
            QMessageBox.warning(
                self,
                "No Translation",
                "Translate the transcript to Khmer first.",
            )
            return

        video_path = self.state.get_video_path()
        if video_path is None:
            QMessageBox.warning(self, "No Video", "Please load a video first.")
            return

        # Show gender assignment dialog before proceeding.
        from ui.components.gender_assign_dialog import GenderAssignDialog
        vocals_path = (
            self.current_timeline_cache.vocals_path
            if self.current_timeline_cache else None
        )
        dialog = GenderAssignDialog(
            segments=list(segments),
            vocals_path=vocals_path,
            duration_ms=self.current_timeline_cache.duration_ms if self.current_timeline_cache else 0,
            parent=self,
        )
        if dialog.exec() != GenderAssignDialog.DialogCode.Accepted:
            return

        # Use the updated segments (with gender + voice assigned).
        segments = dialog.get_segments()
        self.state.set_translation(segments)
        self.transcript_table.set_segments(segments)

        logger.info("Starting TTS for %d segments.", len(segments))
        self.status_bar.set_progress(0, "Starting voice generation…")

        from app.paths import TTS_CACHE_DIR
        tts_dir = TTS_CACHE_DIR / video_path.stem
        tts_dir.mkdir(parents=True, exist_ok=True)

        thread = QThread(self)
        worker = TtsWorker(
            segments=list(segments),
            video_stem=video_path.stem,
            output_dir=tts_dir,
        )

        worker.moveToThread(thread)
        thread.worker = worker
        self.running_threads.append(thread)

        thread.started.connect(worker.run)

        worker.progress_changed.connect(
            lambda p, m: self.status_bar.set_progress(p, m)
        )
        worker.finished.connect(self._on_tts_finished)
        worker.failed.connect(self._on_tts_failed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)

        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot(object)
    def _on_tts_finished(self, segments) -> None:
        count = sum(1 for s in segments if s.audio_path)
        logger.info("TTS finished: %d/%d segments have audio.", count, len(segments))

        self.state.set_translation(segments)
        self.transcript_table.set_segments(segments)

        if self.current_timeline_cache:
            self.timeline_builder_service.attach_tts_segments(
                self.current_timeline_cache, segments
            )
            self.timeline_cache_service.save(self.current_timeline_cache)
            self.timeline_store.load_cache(self.current_timeline_cache)
            self.timeline_editor.set_timeline_store(
                self.timeline_store,
                self.current_timeline_cache.duration_ms,
            )

        # Mix all TTS clips into a single dubbed-voice track and add a stem player.
        self.status_bar.set_progress(98, "Mixing dubbed voice track…")
        self._build_dubbed_player(segments)

        self.status_bar.set_progress(100, f"Voice generated for {count} segments")
        QMessageBox.information(
            self,
            "Voice Generation Complete",
            f"Generated audio for {count}/{len(segments)} segments.\n"
            "Khmer Voice track is now loaded in the timeline.",
        )

    def _build_dubbed_player(self, segments) -> None:
        """Create a position-driven player for the individual TTS segment clips."""
        from services.dubbed_voice_player import DubbedVoicePlayer

        # Discard any previous instance.
        if self._dubbed_voice_player is not None:
            self._dubbed_voice_player.stop()
            self._dubbed_voice_player.deleteLater()
            self._dubbed_voice_player = None

        valid = [s for s in segments if s.audio_path]
        if not valid:
            logger.warning("No TTS audio files to set up dubbed voice player.")
            return

        # Resolve mute state from the timeline cache.
        muted = False
        if self.current_timeline_cache:
            for track in self.current_timeline_cache.tracks:
                if track.id == "track_khmer_voice":
                    muted = track.muted
                    break

        player = DubbedVoicePlayer(valid, parent=self)
        player.set_muted(muted)
        self._dubbed_voice_player = player

        # If main player is already playing, sync immediately.
        if (
            self.video_preview.player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            player.play()
            player.on_position_changed(self.video_preview.player.position())

        logger.info(
            "Dubbed voice player ready: %d segments, muted=%s.", len(valid), muted
        )

    @Slot(str)
    def _on_tts_failed(self, error: str) -> None:
        logger.error("TTS failed: %s", error)
        self.status_bar.set_progress(0, "Voice generation failed")
        QMessageBox.critical(self, "Voice Generation Failed", error)

    # ── Video → MP3 ──────────────────────────────────────────────────────────

    def export_video_to_mp3(self) -> None:
        """Ask for a save path and convert the loaded video's audio to MP3."""
        video_path = self.state.get_video_path()

        if video_path is None:
            QMessageBox.warning(self, "No Video", "Please load a video first.")
            return

        default_name = video_path.stem + ".mp3"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save MP3",
            str(video_path.parent / default_name),
            "MP3 Audio (*.mp3);;All Files (*)",
        )

        if not output_path:
            return

        output_path = Path(output_path)

        logger.info("Exporting MP3: %s → %s", video_path, output_path)
        self.status_bar.set_progress(0, "Starting MP3 export…")

        thread = QThread(self)
        worker = VideoToMp3Worker(video_path=video_path, output_path=output_path)

        worker.moveToThread(thread)
        thread.worker = worker
        self.running_threads.append(thread)

        thread.started.connect(worker.run)

        worker.progress_changed.connect(
            lambda p, m: self.status_bar.set_progress(p, m)
        )
        worker.finished.connect(self._on_mp3_export_finished)
        worker.failed.connect(self._on_mp3_export_failed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)

        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot(str)
    def _on_mp3_export_finished(self, output_path: str) -> None:
        self.status_bar.set_progress(100, f"MP3 saved: {output_path}")
        QMessageBox.information(
            self,
            "MP3 Export Complete",
            f"Audio saved to:\n{output_path}",
        )

    @Slot(str)
    def _on_mp3_export_failed(self, error: str) -> None:
        logger.error("MP3 export failed: %s", error)
        self.status_bar.set_progress(0, "MP3 export failed")
        QMessageBox.critical(self, "MP3 Export Failed", error)

    # ── Export Dubbed Video ───────────────────────────────────────────────────

    def export_dubbed_video(self) -> None:
        """Mix TTS voice + optional background stem with the video and save an MP4."""
        from workers.export_worker import ExportWorker

        video_path = self.state.get_video_path()
        if video_path is None:
            QMessageBox.warning(self, "No Video", "Please load a video first.")
            return

        segments = self.state.get_transcript()
        dubbed = [s for s in segments if s.audio_path]
        if not dubbed:
            QMessageBox.warning(
                self,
                "No Dubbed Voice",
                "Generate Voice first before exporting the dubbed video.",
            )
            return

        default_name = video_path.stem + "_dubbed.mp4"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Dubbed Video",
            str(video_path.parent / default_name),
            "MP4 Video (*.mp4);;All Files (*)",
        )
        if not output_path:
            return

        output_path = Path(output_path)

        bg_path = None
        if self.current_timeline_cache and self.current_timeline_cache.background_path:
            bg_path = Path(self.current_timeline_cache.background_path)
            if not bg_path.exists():
                bg_path = None

        logger.info(
            "Exporting dubbed video: %s → %s (background=%s)",
            video_path,
            output_path,
            bg_path,
        )

        # Pause playback so positionChanged stops firing during the export.
        # This prevents re-entrant paint events on the timeline while the
        # worker thread is being set up and started.
        self.video_preview.player.pause()
        for _player, _audio in self._stem_players.values():
            _player.pause()

        self.status_bar.set_progress(0, "Starting dubbed video export…")

        thread = QThread(self)
        worker = ExportWorker(
            video_path=video_path,
            segments=dubbed,
            output_path=output_path,
            background_path=bg_path,
        )

        worker.moveToThread(thread)
        thread.worker = worker
        self.running_threads.append(thread)

        thread.started.connect(worker.run)
        worker.progress_changed.connect(
            lambda p, m: self.status_bar.set_progress(p, m)
        )
        worker.finished.connect(self._on_export_finished)
        worker.failed.connect(self._on_export_failed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot(str)
    def _on_export_finished(self, output_path: str) -> None:
        self.status_bar.set_progress(100, f"Dubbed video saved: {output_path}")
        QMessageBox.information(
            self,
            "Export Complete",
            f"Dubbed video saved to:\n{output_path}",
        )

    @Slot(str)
    def _on_export_failed(self, error: str) -> None:
        logger.error("Dubbed video export failed: %s", error)
        self.status_bar.set_progress(0, "Export failed")
        QMessageBox.critical(self, "Export Failed", error)

    # ── Import Khmer SRT ──────────────────────────────────────────────────────

    def import_khmer_srt(self) -> None:
        """Let the user pick an existing Khmer SRT and load it as translation."""
        from services.srt_service import SrtService

        srt_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Khmer SRT",
            "",
            "SRT Files (*.srt);;All Files (*)",
        )
        if not srt_path:
            return

        try:
            segments = SrtService().parse(Path(srt_path))
        except Exception as exc:
            logger.exception("Failed to parse Khmer SRT.")
            QMessageBox.critical(self, "Import Failed", str(exc))
            return

        # If we already have an original transcript, copy text into khmer_text.
        existing = self.state.get_transcript()
        if existing and len(existing) == len(segments):
            for orig, imported in zip(existing, segments):
                orig.khmer_text = imported.original_text or imported.khmer_text
            segments = existing
        else:
            for seg in segments:
                if not seg.khmer_text:
                    seg.khmer_text = seg.original_text

        self.state.set_translation(segments)
        self.transcript_table.set_segments(segments)

        self.status_bar.set_progress(
            100,
            f"Khmer SRT imported: {len(segments)} segments",
        )
        QMessageBox.information(
            self,
            "SRT Imported",
            f"Loaded {len(segments)} segments from:\n{srt_path}\n\n"
            "You can now click Generate Voice.",
        )

    # ── Voice Library ─────────────────────────────────────────────────────────

    def _open_voice_library(self) -> None:
        """Open the VoxCPM2 Voice Clone Studio dialog."""
        from ui.components.voxcpm_dialog import VoxCPMDialog
        if not hasattr(self, "_voxcpm_dialog") or self._voxcpm_dialog is None:
            self._voxcpm_dialog = VoxCPMDialog(parent=self)
        self._voxcpm_dialog.show()
        self._voxcpm_dialog.raise_()

    # ── Settings ──────────────────────────────────────────────────────────────

    def show_settings(self) -> None:
        """Open the Settings dialog and apply any changes that were saved."""
        from ui.components.settings_dialog import SettingsDialog

        dialog = SettingsDialog(config=self.config, parent=self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return

        result = dialog.get_result()
        if result is None:
            return

        # Push new model selections into the toolbar so subsequent actions
        # (Auto Transcribe, Translate …) pick up the new choices immediately.
        self.toolbar.apply_settings(
            transcription_provider=result.transcription_provider,
            transcription_model=result.transcription_model,
            translation_provider=result.translation_provider,
            translation_model=result.translation_model,
        )

        # Update the live config reference for fields that are read directly
        # by services (language codes, API keys).  We replace the frozen
        # dataclass with a new one so all existing references stay valid.
        from app.config import AppConfig
        import dataclasses
        self.config = dataclasses.replace(
            self.config,
            transcription_model=result.transcription_model,
            transcription_provider=result.transcription_provider,
            transcription_language=result.transcription_language,
            translation_model=result.translation_model,
            translation_provider=result.translation_provider,
            translation_source_language=result.translation_source_language,
            translation_target_language=result.translation_target_language,
            deepinfra_api_key=result.deepinfra_api_key or self.config.deepinfra_api_key,
            gemini_api_key=result.gemini_api_key or self.config.gemini_api_key,
        )

        logger.info(
            "Settings applied — transcription: %s/%s  translation: %s/%s",
            result.transcription_provider,
            result.transcription_model,
            result.translation_provider,
            result.translation_model,
        )

        self.status_bar.set_progress(100, "Settings saved.")

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

        # Prefer the clean vocals stem (Demucs) over raw video audio when available.
        vocals_path = None
        if self.current_timeline_cache and self.current_timeline_cache.vocals_path:
            candidate = Path(self.current_timeline_cache.vocals_path)
            if candidate.exists():
                vocals_path = candidate
                logger.info("Using vocals stem for transcription: %s", vocals_path)

        # ── lazy model download ───────────────────────────────────────────────
        if selected_provider == "local":
            from ui.components.model_download_dialog import ModelDownloadDialog
            if not ModelDownloadDialog.ensure(selected_provider, selected_model, parent=self):
                self.status_bar.set_progress(0, "Transcription cancelled — model not downloaded.")
                return

        self.status_bar.set_progress(0, "Preparing transcription...")

        thread = QThread(self)
        worker = TranscriptionWorker(
            config=self.config,
            video_path=video_path,
            provider=selected_provider,
            model=selected_model,
            language=self.config.transcription_language,
            vocals_path=vocals_path,
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

        # Show the transcript table immediately.
        self.transcript_table.set_segments(segments)

        # Auto-save SRT next to the source video.
        srt_path = self._auto_save_srt(segments, suffix="")
        saved_msg = f"\n\nSRT saved to:\n{srt_path}" if srt_path else ""

        self.status_bar.set_progress(
            100,
            f"Transcript ready: {len(segments)} segments. Click Translate Khmer.",
        )

        QMessageBox.information(
            self,
            "Transcription Complete",
            f"Generated {len(segments)} transcript segments.{saved_msg}\n\nNext step: click Translate Khmer.",
        )

    def _auto_save_srt(self, segments, suffix: str = "") -> Path | None:
        """Save *segments* as SRT next to the source video. Returns the path or None."""
        from services.srt_service import SrtService
        video_path = self.state.get_video_path()
        if not video_path or not segments:
            logger.warning(
                "_auto_save_srt: skipped - video_path=%s segments=%d",
                video_path,
                len(segments) if segments else 0,
            )
            return None

        # Ensure all segments have a valid start_time before exporting.
        valid = [s for s in segments if s.start_time and s.end_time]
        if not valid:
            logger.warning("_auto_save_srt: no segments with valid timestamps.")
            return None

        srt_path = video_path.parent / f"{video_path.stem}{suffix}.srt"
        try:
            SrtService().export(valid, srt_path)
            logger.info("SRT auto-saved: %s", srt_path)
            return srt_path
        except Exception:
            logger.exception("Failed to auto-save SRT to %s", srt_path)
            return None

    def export_srt(self) -> None:
        """Open a Save dialog and write the current transcript to an SRT file."""
        from services.srt_service import SrtService
        segments = self.state.get_transcript()
        if not segments:
            QMessageBox.warning(self, "No Transcript", "Run Auto Transcribe first.")
            return

        video_path = self.state.get_video_path()
        default_name = (video_path.stem + ".srt") if video_path else "transcript.srt"
        default_dir  = str(video_path.parent) if video_path else str(Path.home() / "Desktop")

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export SRT",
            str(Path(default_dir) / default_name),
            "SRT Subtitles (*.srt);;All Files (*)",
        )
        if not save_path:
            return

        try:
            SrtService().export(segments, Path(save_path))
            self.status_bar.set_progress(100, f"SRT exported: {save_path}")
            QMessageBox.information(self, "SRT Exported", f"Saved to:\n{save_path}")
        except Exception as exc:
            logger.exception("SRT export failed.")
            QMessageBox.critical(self, "Export Failed", str(exc))


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

    def cleanup(self) -> None:
        """Stop all players, quit background threads, and wipe saved timeline caches."""
        logger.info("EditorLayout cleanup started.")

        # Stop the main video player.
        try:
            self.video_preview.player.stop()
        except Exception:
            pass

        # Stop and discard all stem players.
        for track_id, (player, _) in list(self._stem_players.items()):
            try:
                player.stop()
                player.deleteLater()
            except Exception:
                pass
        self._stem_players.clear()

        # Stop the dubbed voice player.
        if self._dubbed_voice_player is not None:
            try:
                self._dubbed_voice_player.stop()
                self._dubbed_voice_player.deleteLater()
            except Exception:
                pass
            self._dubbed_voice_player = None

        # Terminate any running background threads.
        for thread in list(self.running_threads):
            try:
                thread.quit()
                thread.wait(2000)
            except Exception:
                pass
        self.running_threads.clear()

        # Persist current cache so the next session can restore cached steps.
        try:
            if self.current_timeline_cache:
                self.timeline_cache_service.save(self.current_timeline_cache)
                logger.info("Timeline cache saved on close.")
        except Exception:
            logger.exception("Failed to save timeline cache on close.")

        # Reset in-memory state.
        self.current_timeline_cache = None
        self.timeline_store = None

        logger.info("EditorLayout cleanup complete.")

    def on_transcript_changed(self, segments):
        logger.info("Transcript stored with %s segment(s).", len(segments))

        # Keep table hidden until Khmer translation is ready.
        self.transcript_table.hide()

    def on_translation_segments_loaded(self, segments):
        """Called when a new translation arrives from state — refreshes the table."""
        logger.info("Khmer translation ready with %s segment(s).", len(segments))

        self.transcript_table.set_segments(segments)
        self.transcript_table.show()

        self.status_bar.set_progress(
            100,
            f"Khmer translation ready: {len(segments)} segments.",
        )

    def on_table_segments_edited(self, segments):
        """Called when the user edits a cell in the transcript table.

        Persists changes (pitch / speed / vol / text) back to app state so
        the TTS worker picks them up when Generate Voice is triggered later.
        """
        self.state.update_segments_from_table(segments)
        logger.debug("Table edits saved to state (%d segments).", len(segments))


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

        # ── lazy model download ───────────────────────────────────────────────
        if provider == "local_nllb":
            from ui.components.model_download_dialog import ModelDownloadDialog
            if not ModelDownloadDialog.ensure(provider, model, parent=self):
                self.status_bar.set_progress(0, "Translation cancelled — model not downloaded.")
                return

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

        # Auto-save translated SRT alongside the source video.
        srt_path = self._auto_save_srt(segments, suffix="_khmer")
        saved_msg = f"\n\nSRT saved to:\n{srt_path}" if srt_path else ""

        self.status_bar.set_progress(
            100,
            f"Khmer translation complete: {len(segments)} segments",
        )

        QMessageBox.information(
            self,
            "Translation Complete",
            f"Translated {len(segments)} segments to Khmer.{saved_msg}\n\nNext step: click Generate Voice.",
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

    ## Export to CapCut handler
    def export_to_capcut(self):
        if self.current_timeline_cache is None:
            QMessageBox.warning(
                self,
                "No Timeline",
                "Please load a video first.",
            )
            return

        self.status_bar.set_progress(0, "Starting CapCut export...")

        thread = QThread(self)
        worker = CapCutExportWorker(
            cache=self.current_timeline_cache,
        )

        worker.moveToThread(thread)

        thread.worker = worker
        self.running_threads.append(thread)

        thread.started.connect(worker.run)

        worker.progress_changed.connect(self.on_capcut_export_progress)
        worker.finished.connect(self.on_capcut_export_finished)
        worker.failed.connect(self.on_capcut_export_failed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)

        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot(int, str)
    def on_capcut_export_progress(self, value: int, message: str):
        self.status_bar.set_progress(value, message)


    @Slot(object)
    def on_capcut_export_finished(self, project_dir):
        project_dir = Path(project_dir)

        self.status_bar.set_progress(100, "CapCut project ready")

        capcut_opened = self.capcut_app_service.open_capcut()

        if capcut_opened:
            QMessageBox.information(
                self,
                "Exported to CapCut",
                "Your timeline has been exported as a CapCut project.\n\n"
                "CapCut is opening — your project will appear in the project list.\n\n"
                "If you don't see it immediately, close and reopen CapCut.",
            )
        else:
            self.capcut_app_service.open_folder(project_dir)
            QMessageBox.warning(
                self,
                "Exported to CapCut",
                "CapCut project created but CapCut was not found on this machine.\n\n"
                f"Project folder:\n{project_dir}\n\n"
                "Open CapCut manually — the project will appear in its project list.",
            )


    @Slot(str)
    def on_capcut_export_failed(self, message: str):
        logger.error("CapCut export failed: %s", message)

        self.status_bar.clear_progress()
        self.status_bar.set_status("CapCut export failed")

        QMessageBox.critical(
            self,
            "CapCut Export Failed",
            message,
        )