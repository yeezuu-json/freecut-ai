import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.logger import get_logger
from app.paths import find_ffprobe
from models.timeline_cache import TimelineCache
from models.timeline_item import TimelineItem

logger = get_logger(__name__)


class CapCutExportService:
    """
    Creates a native CapCut project inside CapCut's own projects directory
    and registers it in root_meta_info.json so CapCut shows it immediately.

    CapCut project folder layout (reverse-engineered from real projects):

        <MMDD>/
            draft_info.json              ← main timeline (tracks + materials)
            draft_meta_info.json         ← project metadata
            timeline_layout.json         ← dock layout, references timeline_id
            attachment_pc_common.json    ← attachment config (root level)
            draft_agency_config.json
            draft_biz_config.json        ← empty
            key_value.json               ← segment/material analytics
            Timelines/
                project.json             ← project index, references timeline_id
                <timeline_id>/
                    draft_info.json      ← SAME content as root draft_info.json
                    attachment_pc_common.json
                    attachment_editing.json
                    common_attachment/   ← empty dir
            draft_settings/              ← empty dir
            adjust_mask/                 ← empty dir
            matting/                     ← empty dir
            smart_crop/                  ← empty dir
            qr_upload/                   ← empty dir
            subdraft/                    ← empty dir
            common_attachment/           ← empty dir
            Resources/                   ← empty dir
            voices/                      ← our TTS voice clips

    Three distinct UUIDs are used throughout:
        timeline_id   – id in draft_info.json, Timelines folder, layout refs
        timelines_pid – id inside Timelines/project.json
        meta_id       – draft_id in draft_meta_info.json + root_meta_info.json
    """

    NEW_VERSION = "167.0.0"
    CAPCUT_VERSION = 360000

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def find_capcut_projects_dir(self) -> Path:
        if sys.platform == "darwin":
            return (
                Path.home()
                / "Movies"
                / "CapCut"
                / "User Data"
                / "Projects"
                / "com.lveditor.draft"
            )
        elif sys.platform.startswith("win"):
            local_app = os.environ.get(
                "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
            )
            return (
                Path(local_app)
                / "CapCut"
                / "User Data"
                / "Projects"
                / "com.lveditor.draft"
            )
        else:
            raise NotImplementedError(
                "CapCut project export is not supported on this platform."
            )

    def export_capcut_project(
        self,
        cache: TimelineCache,
        project_name: str | None = None,
        on_progress=None,
    ) -> Path:
        """
        Build a native CapCut project from *cache* and register it so CapCut
        shows it in the project list on next open.  Returns the project folder.

        Strategy:
          1. Look for an existing CapCut project to use as a template.
             Copying a real project preserves all quarantine/xattr metadata so
             CapCut accepts it without the "unusual path" error.
          2. If no template exists, fall back to building all files from scratch.
        """
        if not cache.video_path:
            raise ValueError("Timeline cache has no video path.")

        def _p(pct: int, msg: str):
            if on_progress:
                on_progress(pct, msg)

        _p(5, "Locating CapCut project directory…")
        projects_dir = self.find_capcut_projects_dir()
        projects_dir.mkdir(parents=True, exist_ok=True)

        folder_name = self._unique_folder_name(projects_dir)
        project_dir = projects_dir / folder_name

        if not project_name:
            project_name = folder_name

        now_us    = int(time.time() * 1_000_000)
        meta_id   = self._new_uuid()

        logger.info("Creating CapCut project '%s' → %s", project_name, project_dir)

        template_dir = self._find_valid_template(projects_dir)

        if template_dir:
            logger.info("Using template project: %s", template_dir)
            _p(15, "Copying template project…")
            # copytree with copy2 preserves all extended attributes (quarantine)
            shutil.copytree(str(template_dir), str(project_dir),
                            copy_function=shutil.copy2)

            # Remove stale media from template BEFORE copying our files
            for stale in ("voices", "media"):
                stale_dir = project_dir / stale
                if stale_dir.exists():
                    shutil.rmtree(stale_dir, ignore_errors=True)

            # Read platform info from the real project so device IDs are correct
            platform_info: dict | None = None
            try:
                tpl_draft = json.loads(
                    (template_dir / "draft_info.json").read_text(encoding="utf-8")
                )
                platform_info = tpl_draft.get("platform") or tpl_draft.get("last_modified_platform")
            except Exception:
                pass

            _p(30, "Copying media into project…")
            copied_voices = self._copy_media_files(cache, project_dir)

            _p(55, "Building CapCut timeline…")
            timeline_id   = self._new_uuid()
            timelines_pid = self._new_uuid()

            draft_info_data = self._build_draft_info(
                cache=cache,
                timeline_id=timeline_id,
                copied_voices=copied_voices,
                platform_info=platform_info,
            )

            _p(70, "Injecting timeline into project…")
            self._inject_timeline(
                project_dir=project_dir,
                projects_dir=projects_dir,
                draft_info_data=draft_info_data,
                timeline_id=timeline_id,
                timelines_pid=timelines_pid,
                meta_id=meta_id,
                project_name=project_name,
                duration_us=self._ms_to_us(cache.duration_ms),
                now_us=now_us,
            )
        else:
            logger.info("No template found – building project from scratch")
            project_dir.mkdir(parents=True, exist_ok=True)

            _p(20, "Copying media into project…")
            copied_voices = self._copy_media_files(cache, project_dir)

            _p(45, "Building CapCut timeline…")
            timeline_id   = self._new_uuid()
            timelines_pid = self._new_uuid()

            draft_info_data = self._build_draft_info(
                cache=cache,
                timeline_id=timeline_id,
                copied_voices=copied_voices,
            )

            _p(65, "Writing project files…")
            self._write_all_files(
                project_dir=project_dir,
                projects_dir=projects_dir,
                draft_info_data=draft_info_data,
                timeline_id=timeline_id,
                timelines_pid=timelines_pid,
                meta_id=meta_id,
                project_name=project_name,
                duration_us=self._ms_to_us(cache.duration_ms),
                now_us=now_us,
            )

        _p(88, "Registering project with CapCut…")
        self._register_project(
            projects_dir=projects_dir,
            project_dir=project_dir,
            meta_id=meta_id,
            project_name=project_name,
            duration_us=self._ms_to_us(cache.duration_ms),
            now_us=now_us,
        )

        logger.info("CapCut project written: %s", project_dir)
        return project_dir

    # ------------------------------------------------------------------ #
    # Write all project files
    # ------------------------------------------------------------------ #

    def _write_all_files(
        self,
        project_dir: Path,
        projects_dir: Path,
        draft_info_data: dict,
        timeline_id: str,
        timelines_pid: str,
        meta_id: str,
        project_name: str,
        duration_us: int,
        now_us: int,
    ) -> None:
        now_s = now_us // 1_000_000
        ts_hex = format(now_s, "x").lower()
        draft_info_json = json.dumps(draft_info_data, ensure_ascii=False, indent=2)

        common_attachment_data = self._attachment_pc_common()
        editing_data = self._attachment_editing()

        # ---- root-level files ---------------------------------------- #
        files: list[tuple[Path, str | bytes]] = [
            (project_dir / "draft_info.json", draft_info_json),
            (project_dir / "draft_meta_info.json", json.dumps(
                self._build_draft_meta_info(
                    project_name=project_name,
                    meta_id=meta_id,
                    project_dir=project_dir,
                    projects_dir=projects_dir,
                    duration_us=duration_us,
                    now_us=now_us,
                ), ensure_ascii=False, indent=2)),
            (project_dir / "timeline_layout.json", json.dumps({
                "dockItems": [{"dockIndex": 0, "ratio": 1,
                               "timelineIds": [timeline_id],
                               "timelineNames": ["Timeline 01"]}],
                "layoutOrientation": 1,
            }, ensure_ascii=False)),
            (project_dir / "attachment_pc_common.json",
             json.dumps(common_attachment_data, ensure_ascii=False)),
            (project_dir / "attachment_editing.json",
             json.dumps(editing_data, ensure_ascii=False)),
            (project_dir / "draft_agency_config.json", json.dumps({
                "is_auto_agency_enabled": False, "is_auto_agency_popup": False,
                "is_single_agency_mode": False, "marterials": None,
                "use_converter": False, "video_resolution": 720,
            }, ensure_ascii=False)),
            (project_dir / "draft_biz_config.json", b""),
            (project_dir / "key_value.json", "{}"),
            (project_dir / "draft_virtual_store.json", json.dumps({
                "draft_materials": [],
                "draft_virtual_store": [
                    {"type": 0, "value": [{"creation_time": 0, "display_name": "",
                                           "filter_type": 0, "id": "", "import_time": 0,
                                           "import_time_us": 0, "sort_sub_type": 0,
                                           "sort_type": 0, "subdraft_filter_type": 0}]},
                    {"type": 1, "value": []},
                    {"type": 2, "value": []},
                ],
            }, ensure_ascii=False)),
            (project_dir / "performance_opt_info.json",
             json.dumps({"manual_cancle_precombine_segs": None,
                         "need_auto_precombine_segs": None}, ensure_ascii=False)),
            # draft_settings is an INI file, not a directory
            (project_dir / "draft_settings",
             f"[General]\ncloud_last_modify_platform=mac\n"
             f"draft_create_time={now_s}\ndraft_last_edit_time={now_s}\n"
             f"real_edit_keys=0\nreal_edit_seconds=0\n"),
        ]

        # ---- common_attachment files (root level) -------------------- #
        (project_dir / "common_attachment").mkdir(exist_ok=True)
        for name, content in self._common_attachment_files():
            files.append((project_dir / "common_attachment" / name, content))

        # ---- Timelines/project.json ---------------------------------- #
        timelines_dir = project_dir / "Timelines"
        timelines_dir.mkdir(exist_ok=True)
        files.append((timelines_dir / "project.json", json.dumps({
            "config": {"color_space": -1, "render_index_track_mode_on": False,
                       "use_float_render": False},
            "create_time": now_us,
            "id": timelines_pid,
            "main_timeline_id": timeline_id,
            "timelines": [{"create_time": now_us, "id": timeline_id,
                           "is_marked_delete": False, "name": "Timeline 01",
                           "update_time": now_us}],
            "update_time": now_us,
            "version": 0,
        }, ensure_ascii=False)))

        # ---- Timelines/<timeline_id>/ -------------------------------- #
        tl_folder = timelines_dir / timeline_id
        tl_folder.mkdir(exist_ok=True)
        (tl_folder / "common_attachment").mkdir(exist_ok=True)

        files.append((tl_folder / "draft_info.json", draft_info_json))
        files.append((tl_folder / "attachment_pc_common.json",
                      json.dumps(common_attachment_data, ensure_ascii=False)))
        files.append((tl_folder / "attachment_editing.json",
                      json.dumps(editing_data, ensure_ascii=False)))
        for name, content in self._common_attachment_files():
            files.append((tl_folder / "common_attachment" / name, content))

        # ---- other empty dirs ---------------------------------------- #
        for name in ("adjust_mask", "matting", "smart_crop",
                     "qr_upload", "subdraft", "Resources"):
            (project_dir / name).mkdir(exist_ok=True)

        # ---- write all files and stamp quarantine attribute ----------- #
        for path, content in files:
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")

        # Stamp com.apple.quarantine on every file so CapCut recognises
        # the project as one created by CapCut (not "unusual path").
        self._stamp_capcut_quarantine(project_dir, ts_hex)

    # ------------------------------------------------------------------ #
    # common_attachment file content helper
    # ------------------------------------------------------------------ #

    def _common_attachment_files(self) -> list[tuple[str, str]]:
        return [
            ("attachment_action_scene.json",
             json.dumps({"action_scene": {"removed_segments": [], "segment_infos": []}},
                        ensure_ascii=False)),
            ("attachment_gen_ai_info.json",
             json.dumps({"gen_ai": {
                 "ai_func_config": {"ai_common_configs": [], "ai_effect_configs": [],
                                    "ai_func_list": [], "aigc_generation_configs": []},
                 "cc_agent_info": {"agent_stringent_section_id_list": [],
                                   "agent_stringent_used_tool_list": [],
                                   "is_agent_stringent_used": False,
                                   "is_agent_used": False, "tool_list": []},
                 "id": "", "scene": "", "version": "1.0.0",
             }}, ensure_ascii=False)),
            ("attachment_pc_timeline.json",
             json.dumps({"reference_lines_config": {"horizontal_lines": [],
                                                    "is_lock": False, "is_visible": False,
                                                    "vertical_lines": []},
                         "safe_area_type": 0}, ensure_ascii=False)),
            ("attachment_plugin_draft.json",
             json.dumps({"plugin_draft": {"plugin_segments": [], "version": "1.0.0"}},
                        ensure_ascii=False)),
            ("attachment_script_video.json",
             json.dumps({"script_video": {
                 "attachment_valid": False, "language": "", "overdub_recover": [],
                 "overdub_sentence_ids": [], "parts": [], "sync_subtitle": False,
                 "translate_segments": [], "translate_type": "", "version": "1.0.0",
             }}, ensure_ascii=False)),
        ]

    # ------------------------------------------------------------------ #
    # macOS quarantine attribute
    # ------------------------------------------------------------------ #

    def _stamp_capcut_quarantine(self, project_dir: Path, ts_hex: str) -> None:
        """
        Set com.apple.quarantine on every file in the project directory.
        CapCut verifies this attribute to confirm a project belongs to it.
        Without it CapCut shows 'unusual path' and refuses to open the project.
        """
        if sys.platform != "darwin":
            return

        quarantine_value = f"0086;{ts_hex};CapCut;"

        for p in project_dir.rglob("*"):
            if p.is_file():
                try:
                    subprocess.run(
                        ["xattr", "-w", "com.apple.quarantine", quarantine_value, str(p)],
                        capture_output=True, check=False,
                    )
                except Exception:
                    logger.warning("Could not set quarantine attr on %s", p)

    def _stamp_quarantine_files(self, paths: list[Path], ts_hex: str) -> None:
        """Stamp quarantine only on specific files (used after injecting into template)."""
        if sys.platform != "darwin":
            return
        quarantine_value = f"0086;{ts_hex};CapCut;"
        for p in paths:
            if p.exists() and p.is_file():
                try:
                    subprocess.run(
                        ["xattr", "-w", "com.apple.quarantine", quarantine_value, str(p)],
                        capture_output=True, check=False,
                    )
                except Exception:
                    logger.warning("Could not set quarantine attr on %s", p)

    # ------------------------------------------------------------------ #
    # Template discovery
    # ------------------------------------------------------------------ #

    def _find_valid_template(self, projects_dir: Path) -> Path | None:
        """
        Find an existing real CapCut project folder to use as a template.
        Using a real project's directory structure ensures all system-level
        attributes (quarantine, etc.) are already correct.

        A "real" CapCut project is one whose draft_info.json:
          1. Has com.apple.quarantine set (macOS only)
          2. Has last_modified_platform with app_source == "cc"  (CapCut-authored)

        We prefer projects matching both criteria; fall back to quarantine-only.
        """
        if not projects_dir.exists():
            return None

        best: tuple[float, Path] | None = None     # real CapCut project
        fallback: tuple[float, Path] | None = None  # any quarantined project

        for entry in projects_dir.iterdir():
            if not entry.is_dir():
                continue
            draft_info = entry / "draft_info.json"
            if not draft_info.exists():
                continue

            # Check quarantine attribute (macOS)
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["xattr", "-l", str(draft_info)],
                    capture_output=True, text=True, check=False,
                )
                if "com.apple.quarantine" not in result.stdout:
                    continue

            mtime = draft_info.stat().st_mtime

            # Check if this was actually written by CapCut (not by us)
            is_real_capcut = False
            try:
                data = json.loads(draft_info.read_text(encoding="utf-8"))
                plat = data.get("last_modified_platform") or data.get("platform") or {}
                is_real_capcut = plat.get("app_source") == "cc"
            except Exception:
                pass

            if is_real_capcut:
                if best is None or mtime > best[0]:
                    best = (mtime, entry)
            else:
                if fallback is None or mtime > fallback[0]:
                    fallback = (mtime, entry)

        if best:
            return best[1]
        if fallback:
            return fallback[1]
        return None

    # ------------------------------------------------------------------ #
    # Template injection
    # ------------------------------------------------------------------ #

    def _inject_timeline(
        self,
        project_dir: Path,
        projects_dir: Path,
        draft_info_data: dict,
        timeline_id: str,
        timelines_pid: str,
        meta_id: str,
        project_name: str,
        duration_us: int,
        now_us: int,
    ) -> None:
        """
        Replace the timeline content in a copied-template project directory.
        All files not explicitly rewritten here keep their original xattrs from
        the template (which is why this approach avoids the 'unusual path' error).
        """
        now_s = now_us // 1_000_000
        ts_hex = format(now_s, "x").lower()
        draft_info_json = json.dumps(draft_info_data, ensure_ascii=False, indent=2)

        # ---- Find old timeline_id from template's draft_info.json -------- #
        old_timeline_id: str | None = None
        old_draft_info_path = project_dir / "draft_info.json"
        if old_draft_info_path.exists():
            try:
                old_data = json.loads(old_draft_info_path.read_text(encoding="utf-8"))
                old_timeline_id = old_data.get("id")
            except Exception:
                pass

        # ---- Overwrite root-level files that carry timeline content ------ #
        modified_files: list[Path] = []

        def _write(path: Path, content: str | bytes) -> None:
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
            modified_files.append(path)

        _write(project_dir / "draft_info.json", draft_info_json)

        _write(project_dir / "draft_meta_info.json", json.dumps(
            self._build_draft_meta_info(
                project_name=project_name,
                meta_id=meta_id,
                project_dir=project_dir,
                projects_dir=projects_dir,
                duration_us=duration_us,
                now_us=now_us,
            ), ensure_ascii=False, indent=2))

        _write(project_dir / "timeline_layout.json", json.dumps({
            "dockItems": [{"dockIndex": 0, "ratio": 1,
                           "timelineIds": [timeline_id],
                           "timelineNames": ["Timeline 01"]}],
            "layoutOrientation": 1,
        }, ensure_ascii=False))

        _write(project_dir / "draft_settings",
               f"[General]\ncloud_last_modify_platform=mac\n"
               f"draft_create_time={now_s}\ndraft_last_edit_time={now_s}\n"
               f"real_edit_keys=0\nreal_edit_seconds=0\n")

        # ---- Timelines directory ----------------------------------------- #
        timelines_dir = project_dir / "Timelines"
        timelines_dir.mkdir(exist_ok=True)

        # Rename old timeline folder → new timeline_id
        if old_timeline_id and old_timeline_id != timeline_id:
            old_tl_folder = timelines_dir / old_timeline_id
            new_tl_folder = timelines_dir / timeline_id
            if old_tl_folder.exists():
                old_tl_folder.rename(new_tl_folder)
            else:
                new_tl_folder.mkdir(exist_ok=True)
                (new_tl_folder / "common_attachment").mkdir(exist_ok=True)
        else:
            new_tl_folder = timelines_dir / timeline_id
            new_tl_folder.mkdir(exist_ok=True)
            (new_tl_folder / "common_attachment").mkdir(exist_ok=True)

        _write(timelines_dir / "project.json", json.dumps({
            "config": {"color_space": -1, "render_index_track_mode_on": False,
                       "use_float_render": False},
            "create_time": now_us,
            "id": timelines_pid,
            "main_timeline_id": timeline_id,
            "timelines": [{"create_time": now_us, "id": timeline_id,
                           "is_marked_delete": False, "name": "Timeline 01",
                           "update_time": now_us}],
            "update_time": now_us,
            "version": 0,
        }, ensure_ascii=False))

        _write(new_tl_folder / "draft_info.json", draft_info_json)

        # ---- Re-stamp quarantine on every file we just (re)wrote --------- #
        # Files copied from the template already have valid quarantine xattrs;
        # we only need to stamp the ones we overwrote.
        self._stamp_quarantine_files(modified_files, ts_hex)
        # Also stamp the renamed timeline folder's files
        for p in new_tl_folder.rglob("*"):
            if p.is_file():
                self._stamp_quarantine_files([p], ts_hex)

    # ------------------------------------------------------------------ #
    # Folder name helper
    # ------------------------------------------------------------------ #

    def _unique_folder_name(self, projects_dir: Path) -> str:
        """
        CapCut names projects as MMDD, then MMDD (1), MMDD (2), ...
        We follow the same convention.
        """
        base = datetime.now().strftime("%m%d")
        if not (projects_dir / base).exists():
            return base
        idx = 1
        while (projects_dir / f"{base} ({idx})").exists():
            idx += 1
        return f"{base} ({idx})"

    # ------------------------------------------------------------------ #
    # Media file copy  (voices + all other non-video audio)
    # ------------------------------------------------------------------ #

    def _copy_media_files(
        self, cache: TimelineCache, project_dir: Path
    ) -> dict[str, str]:
        """
        Copy every audio item that lives at a temporary or session-only path
        into the project's media folder so CapCut can always find them.

        Dubbed-voice segments  → project/voices/segment_NNNN.ext
        All other audio items  → project/media/<original-filename>
        Video items            → referenced by their original on-disk path
                                 (user files, not temp; no copy needed)
        """
        voices_dir = project_dir / "voices"
        media_dir  = project_dir / "media"
        copied: dict[str, str] = {}

        for item in cache.items:
            if not item.source_path:
                continue
            source = Path(item.source_path)
            if not source.exists():
                logger.warning("Source file missing, skipping: %s", source)
                continue

            if item.type == "dubbed_voice":
                filename = (
                    f"segment_{int(item.linked_segment_id):04d}{source.suffix}"
                    if item.linked_segment_id
                    else source.name
                )
                voices_dir.mkdir(parents=True, exist_ok=True)
                target = voices_dir / filename
                shutil.copy2(source, target)
                copied[str(source)] = str(target)

            elif item.type in ("audio", "stem", "music") or (
                item.type != "video"
                and source.suffix.lower() in (".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg")
            ):
                # Copy non-video audio (stems, background music, etc.)
                media_dir.mkdir(parents=True, exist_ok=True)
                target = media_dir / source.name
                # Avoid overwriting a different file that happens to share the name
                if target.exists() and target.stat().st_size != source.stat().st_size:
                    stem, suffix = source.stem, source.suffix
                    target = media_dir / f"{stem}_{self._new_uuid()[:8]}{suffix}"
                shutil.copy2(source, target)
                copied[str(source)] = str(target)

        return copied

    # ------------------------------------------------------------------ #
    # draft_info.json  (main CapCut timeline file)
    # ------------------------------------------------------------------ #

    def _build_draft_info(
        self,
        cache: TimelineCache,
        timeline_id: str,
        copied_voices: dict[str, str],
        platform_info: dict | None = None,
    ) -> dict:
        duration_us = self._ms_to_us(cache.duration_ms)
        video_materials: list[dict] = []
        audio_materials: list[dict] = []
        tracks: list[dict] = []

        track_items: dict[str, list[TimelineItem]] = defaultdict(list)
        for item in cache.items:
            if item.source_path:
                track_items[item.track_id].append(item)

        for track in sorted(cache.tracks, key=lambda t: t.order):
            items = track_items.get(track.id, [])
            if not items:
                continue

            is_video = track.kind == "video"
            segments: list[dict] = []

            for item in sorted(items, key=lambda i: i.from_frame):
                actual_path = copied_voices.get(item.source_path, item.source_path)
                if not Path(actual_path).exists():
                    logger.warning("File not found, skipping: %s", actual_path)
                    continue

                start_us = self._frames_to_us(item.from_frame, cache.fps)
                dur_us   = self._frames_to_us(item.duration_in_frames, cache.fps)
                volume   = 0.0 if item.muted else float(item.volume)
                mat_id   = self._new_uuid()
                seg_id   = self._new_uuid()

                if is_video:
                    video_materials.append(
                        self._make_video_material(mat_id, actual_path, dur_us)
                    )
                    segments.append(
                        self._make_video_segment(seg_id, mat_id, start_us, dur_us, volume)
                    )
                else:
                    # Use the exact file duration for source_timerange so CapCut
                    # reads the entire audio file even if frame-rounding made
                    # dur_us slightly shorter than the real file.
                    file_dur_us = self._get_file_duration_us(actual_path) or dur_us
                    name = item.label or Path(actual_path).stem
                    audio_materials.append(
                        self._make_audio_material(mat_id, actual_path, file_dur_us, name)
                    )
                    segments.append(
                        self._make_audio_segment(
                            seg_id, mat_id, start_us,
                            target_dur_us=dur_us,
                            source_dur_us=file_dur_us,
                            volume=volume,
                        )
                    )

            if segments:
                tracks.append(
                    self._make_track(
                        track_id=self._new_uuid(),
                        track_type="video" if is_video else "audio",
                        track_name=track.name,
                        segments=segments,
                    )
                )

        # Use platform info from template if available; otherwise use safe defaults
        _platform = platform_info or {
            "os": "mac" if sys.platform == "darwin" else "windows",
            "os_version": "",
            "app_id": 359289,
            "app_version": "8.5.0",
            "app_source": "cc",
            "device_id": "",
            "hard_disk_id": "",
            "mac_address": "",
        }

        return {
            "id": timeline_id,
            "version": self.CAPCUT_VERSION,
            "new_version": self.NEW_VERSION,
            "name": "",
            "duration": duration_us,
            "create_time": 0,
            "update_time": 0,
            "fps": float(cache.fps),
            "is_drop_frame_timecode": False,
            "color_space": 0,
            "draft_type": "video",
            "cover": None,
            "path": "",
            "extra_info": None,
            "source": "default",
            "config": {
                "video_mute": False,
                "record_audio_last_index": 1,
                "extract_audio_last_index": 1,
                "original_sound_last_index": 1,
                "subtitle_recognition_id": "",
                "subtitle_taskinfo": [],
                "lyrics_recognition_id": "",
                "lyrics_taskinfo": [],
                "subtitle_sync": True,
                "lyrics_sync": True,
                "voice_change_sync": False,
                "sticker_max_index": 1,
                "adjust_max_index": 1,
                "material_save_mode": 0,
                "export_range": None,
                "maintrack_adsorb": True,
                "combination_max_index": 1,
                "attachment_info": [],
                "zoom_info_params": None,
                "system_font_list": [],
                "multi_language_mode": "none",
                "multi_language_main": "none",
                "multi_language_current": "none",
                "multi_language_list": [],
                "subtitle_keywords_config": None,
                "use_float_render": False,
            },
            "canvas_config": {
                "ratio": "original",
                "width": 1920,
                "height": 1080,
                "background": None,
            },
            "tracks": tracks,
            "group_container": None,
            "materials": {
                "videos": video_materials,
                "audios": audio_materials,
                "images": [],
                "texts": [],
                "effects": [],
                "stickers": [],
                "canvases": [],
                "flowers": [],
                "transitions": [],
                "filters": [],
                "adjusts": [],
                "handwrites": [],
                "speeds": [],
                "vocal_beautifys": [],
                "vocal_separations": [],
                "sound_channel_mappings": [],
                "beats": [],
                "shapes": [],
                "chromas": [],
                "masks": [],
                "material_animations": [],
                "hsl": [],
                "color_curves": [],
                "loudness": [],
                "manual_deformations": [],
                "placeholders": [],
                "primary_color_wheels": [],
                "realtime_denoises": [],
                "smart_crops": [],
                "smart_relights": [],
                "tail_leaders": [],
                "text_templates": [],
                "time_marks": [],
                "video_effects": [],
                "video_trackings": [],
                "plugin_effects": [],
                "green_screens": [],
            },
            "keyframes": {
                "adjusts": [], "audios": [], "effects": [],
                "filters": [], "handwrites": [], "stickers": [],
                "texts": [], "videos": [],
            },
            "keyframe_graph_list": [],
            "relationships": [],
            "mutable_config": None,
            "static_cover_image_path": "",
            "retouch_cover": None,
            "time_marks": None,
            "lyrics_effects": [],
            "free_render_index_mode_on": False,
            "render_index_track_mode_on": True,
            "platform": _platform,
            "last_modified_platform": _platform,
            "function_assistant_info": {
                "smart_rec_applied": False, "fixed_rec_applied": False,
                "auto_adjust": False, "auto_adjust_segid_list": [],
                "color_correction": False, "color_correction_segid_list": [],
                "enhance_quality": False, "smooth_slow_motion": False,
                "deflicker_segid_list": [], "video_noise_segid_list": [],
                "enhance_quality_segid_list": [], "smart_segid_list": [],
                "retouch": False, "retouch_segid_list": [],
                "enhande_voice": False, "enhance_voice_segid_list": [],
                "audio_noise_segid_list": [], "auto_caption": False,
                "auto_caption_segid_list": [], "auto_caption_template_id": "",
                "caption_opt": False, "caption_opt_segid_list": [],
                "eye_correction": False, "eye_correction_segid_list": [],
                "normalize_loudness": False, "normalize_loudness_segid_list": [],
                "normalize_loudness_audio_denoise_segid_list": [],
                "auto_adjust_fixed": False, "auto_adjust_fixed_value": 50.0,
                "color_correction_fixed": False, "color_correction_fixed_value": 50.0,
                "normalize_loudness_fixed": False, "enhande_voice_fixed": False,
                "retouch_fixed": False, "enhance_quality_fixed": False,
                "smooth_slow_motion_fixed": False,
                "fps": {"num": 0, "den": 1},
            },
            "smart_ads_info": {"page_from": "", "routine": "", "draft_url": ""},
            "uneven_animation_template_info": {
                "composition": "", "content": "", "order": "",
                "sub_template_info_list": [],
            },
        }

    # ------------------------------------------------------------------ #
    # draft_meta_info.json
    # ------------------------------------------------------------------ #

    def _build_draft_meta_info(
        self,
        project_name: str,
        meta_id: str,
        project_dir: Path,
        projects_dir: Path,
        duration_us: int,
        now_us: int,
    ) -> dict:
        return {
            "cloud_draft_cover": False,
            "cloud_draft_sync": False,
            "cloud_package_completed_time": "",
            "draft_cloud_capcut_purchase_info": "",
            "draft_cloud_last_action_download": False,
            "draft_cloud_package_type": "",
            "draft_cloud_purchase_info": "",
            "draft_cloud_template_id": "",
            "draft_cloud_tutorial_info": "",
            "draft_cloud_videocut_purchase_info": "",
            "draft_cover": "draft_cover.jpg",
            "draft_deeplink_url": "",
            "draft_enterprise_info": {
                "draft_enterprise_extra": "",
                "draft_enterprise_id": "",
                "draft_enterprise_name": "",
                "enterprise_material": [],
            },
            "draft_fold_path": str(project_dir),
            "draft_id": meta_id,
            "draft_is_ae_produce": False,
            "draft_is_ai_packaging_used": False,
            "draft_is_ai_shorts": False,
            "draft_is_ai_translate": False,
            "draft_is_article_video_draft": False,
            "draft_is_cloud_temp_draft": False,
            "draft_is_from_deeplink": "false",
            "draft_is_invisible": False,
            "draft_is_web_article_video": False,
            "draft_materials": [
                {"type": 0, "value": []},
                {"type": 1, "value": []},
                {"type": 2, "value": []},
                {"type": 3, "value": []},
                {"type": 6, "value": []},
                {"type": 7, "value": []},
                {"type": 8, "value": []},
            ],
            "draft_materials_copied_info": [],
            "draft_name": project_name,
            "draft_need_rename_folder": False,
            "draft_new_version": "",
            "draft_removable_storage_device": "",
            "draft_root_path": str(projects_dir),
            "draft_segment_extra_info": [],
            "draft_timeline_materials_size_": 0,
            "draft_type": "",
            "draft_web_article_video_enter_from": "",
            "tm_draft_cloud_completed": "",
            "tm_draft_cloud_entry_id": -1,
            "tm_draft_cloud_modified": 0,
            "tm_draft_cloud_parent_entry_id": -1,
            "tm_draft_cloud_space_id": -1,
            "tm_draft_cloud_user_id": -1,
            "tm_draft_create": now_us,
            "tm_draft_modified": now_us,
            "tm_draft_removed": 0,
            "tm_duration": duration_us,
        }

    # ------------------------------------------------------------------ #
    # Companion JSON helpers
    # ------------------------------------------------------------------ #

    def _attachment_pc_common(self) -> dict:
        empty_report = {
            "caption_id_list": [], "commercial_material": "",
            "material_source": "", "method": "", "page_from": "",
            "style": "", "task_id": "", "text_style": "", "tos_id": "",
            "video_category": "",
        }
        return {
            "ai_packaging_infos": [],
            "ai_packaging_report_info": empty_report,
            "broll": {"ai_packaging_infos": [], "ai_packaging_report_info": empty_report},
            "commercial_music_category_ids": [],
            "pc_feature_flag": 0,
            "recognize_tasks": [],
            "reference_lines_config": {
                "horizontal_lines": [], "is_lock": False,
                "is_visible": False, "vertical_lines": [],
            },
            "safe_area_type": 0,
            "template_item_infos": [],
            "unlock_template_ids": [],
        }

    def _attachment_editing(self) -> dict:
        return {
            "editing_draft": {
                "ai_remove_filter_words": {"enter_source": "", "right_id": ""},
                "ai_shorts_info": {"report_params": "", "type": 0},
                "cover_extra_info": {
                    "draft_id": "", "position": 0,
                    "select_segment_id": "", "select_segment_source_start": 0,
                    "select_segment_target_start": 0, "type": 1,
                },
                "crop_info_extra": {
                    "crop_mirror_type": 0, "crop_rotate": 0.0,
                    "crop_rotate_total": 0.0,
                },
                "digital_human_template_to_video_info": {
                    "has_upload_material": False, "template_type": 0,
                },
                "draft_used_recommend_function": "",
                "edit_type": 0,
                "eye_correct_enabled_multi_face_time": 0,
                "has_adjusted_render_layer": False,
                "image_ai_chat_info": {
                    "before_chat_edit": False, "draft_modify_time": 0,
                    "keyword_content": "", "keyword_type": "",
                    "message_id": "", "model_name": "", "need_restore": False,
                    "picture_id": "", "prompt_content": "", "prompt_from": "",
                    "sugs_info": [],
                },
                "is_open_expand_player": False,
                "is_template_text_ai_generate": False,
                "is_use_adjust": False,
                "is_use_ai_expand": False,
                "is_use_ai_remove": False,
                "is_use_ai_video": False,
                "is_use_audio_separation": False,
                "is_use_chroma_key": False,
                "is_use_curve_speed": False,
                "is_use_digital_human": False,
                "is_use_edit_multi_camera": False,
                "is_use_lip_sync": False,
                "is_use_lock_object": False,
                "is_use_loudness_unify": False,
                "is_use_noise_reduction": False,
                "is_use_one_click_beauty": False,
                "is_use_one_click_ultra_hd": False,
                "is_use_retouch_face": False,
                "is_use_smart_adjust_color": False,
                "is_use_smart_body_beautify": False,
                "is_use_smart_motion": False,
                "is_use_subtitle_recognition": False,
                "is_use_text_to_audio": False,
                "material_edit_session": {
                    "material_edit_info": [], "session_id": "", "session_time": 0,
                },
                "paste_segment_list": [],
                "profile_entrance_type": "",
                "publish_enter_from": "",
                "publish_type": "",
                "single_function_type": 0,
                "text_convert_case_types": [],
                "version": "1.0.0",
                "video_recording_create_draft": "",
            }
        }

    # ------------------------------------------------------------------ #
    # root_meta_info.json registration
    # ------------------------------------------------------------------ #

    def _register_project(
        self,
        projects_dir: Path,
        project_dir: Path,
        meta_id: str,
        project_name: str,
        duration_us: int,
        now_us: int,
    ) -> None:
        meta_path = projects_dir / "root_meta_info.json"
        if meta_path.exists():
            try:
                root_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Could not parse root_meta_info.json; creating fresh.")
                root_meta = {
                    "all_draft_store": [], "draft_ids": 0,
                    "root_path": str(projects_dir),
                }
        else:
            root_meta = {
                "all_draft_store": [], "draft_ids": 0,
                "root_path": str(projects_dir),
            }

        entry = {
            "cloud_draft_cover": False,
            "cloud_draft_sync": False,
            "draft_cloud_last_action_download": False,
            "draft_cloud_purchase_info": "",
            "draft_cloud_template_id": "",
            "draft_cloud_tutorial_info": "",
            "draft_cloud_videocut_purchase_info": "",
            "draft_cover": str(project_dir / "draft_cover.jpg"),
            "draft_fold_path": str(project_dir),
            "draft_id": meta_id,
            "draft_is_ai_shorts": False,
            "draft_is_cloud_temp_draft": False,
            "draft_is_invisible": False,
            "draft_is_web_article_video": False,
            "draft_json_file": str(project_dir / "draft_info.json"),
            "draft_name": project_name,
            "draft_new_version": "",
            "draft_root_path": str(projects_dir),
            "draft_timeline_materials_size": 0,
            "draft_type": "",
            "draft_web_article_video_enter_from": "",
            "streaming_edit_draft_ready": True,
            "tm_draft_cloud_completed": "",
            "tm_draft_cloud_entry_id": -1,
            "tm_draft_cloud_modified": 0,
            "tm_draft_cloud_parent_entry_id": -1,
            "tm_draft_cloud_space_id": -1,
            "tm_draft_cloud_user_id": -1,
            "tm_draft_create": now_us,
            "tm_draft_modified": now_us,
            "tm_draft_removed": 0,
            "tm_duration": duration_us,
        }

        all_drafts: list = root_meta.get("all_draft_store", [])
        all_drafts.insert(0, entry)
        root_meta["all_draft_store"] = all_drafts
        root_meta["draft_ids"] = root_meta.get("draft_ids", 0) + 1
        root_meta["root_path"] = str(projects_dir)

        meta_path.write_text(
            json.dumps(root_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Registered project '%s' in root_meta_info.json", project_name)

    # ------------------------------------------------------------------ #
    # Material builders
    # ------------------------------------------------------------------ #

    def _make_video_material(
        self, mat_id: str, file_path: str, duration_us: int
    ) -> dict:
        p = Path(file_path)
        now_s = int(time.time())
        return {
            "id": mat_id,
            "unique_id": "",
            "type": "video",
            "duration": duration_us,
            "path": file_path,
            "media_path": "",
            "local_id": "",
            "has_audio": True,
            "reverse_path": "",
            "intensifies_path": "",
            "reverse_intensifies_path": "",
            "intensifies_audio_path": "",
            "cartoon_path": "",
            "width": 1920,
            "height": 1080,
            "category_id": "",
            "category_name": "local",
            "material_id": "",
            "material_name": p.name,
            "material_url": "",
            "crop": {
                "upper_left_x": 0.0, "upper_left_y": 0.0,
                "upper_right_x": 1.0, "upper_right_y": 0.0,
                "lower_left_x": 0.0, "lower_left_y": 1.0,
                "lower_right_x": 1.0, "lower_right_y": 1.0,
            },
            "crop_ratio": "free",
            "audio_fade": None,
            "crop_scale": 1.0,
            "extra_type_option": 0,
            "stable": {
                "stable_level": 0,
                "matrix_path": "",
                "time_range": {"start": 0, "duration": 0},
            },
            "import_time": now_s,
            "import_time_ms": int(now_s * 1_000_000),
            "item_source": 1,
            "md5": "",
            "metetype": "video",
            "roughcut_time_range": {"duration": duration_us, "start": 0},
            "sub_time_range": {"duration": -1, "start": -1},
        }

    def _make_audio_material(
        self, mat_id: str, file_path: str, duration_us: int, name: str
    ) -> dict:
        p = Path(file_path)
        return {
            "id": mat_id,
            "app_id": "",
            "category_id": "",
            "category_name": "local",
            "check_flag": 1,
            "duration": duration_us,
            "effect_id": "",
            "file_path": file_path,
            "formula_id": "",
            "intensifies_path": "",
            "is_ai_clone_tone": False,
            "is_text_edit_overdub": False,
            "is_ugc": False,
            "local_material_id": self._new_uuid(),
            "music_id": self._new_uuid(),
            "name": name or p.stem,
            "path": file_path,
            "query": "",
            "request_id": "",
            "resource_id": "",
            "search_id": "",
            "source_from": "local",
            "source_platform": 0,
            "team_id": "",
            "text": "",
            "tone_effect_id": "",
            "tone_effect_name": "",
            "type": "extract_music",
            "wave_points": [],
        }

    # ------------------------------------------------------------------ #
    # Segment builders
    # ------------------------------------------------------------------ #

    def _make_video_segment(
        self, seg_id: str, mat_id: str, start_us: int, duration_us: int, volume: float
    ) -> dict:
        return {
            "id": seg_id,
            "material_id": mat_id,
            "source_timerange": {"start": 0, "duration": duration_us},
            "target_timerange": {"start": start_us, "duration": duration_us},
            "render_timerange": {"start": 0, "duration": 0},
            "desc": "",
            "state": 0,
            "speed": 1.0,
            "is_loop": False,
            "is_tone_modify": False,
            "reverse": False,
            "intensifies_audio": False,
            "cartoon": False,
            "volume": volume,
            "last_nonzero_volume": max(volume, 0.01),
            "clip": {
                "scale": {"x": 1.0, "y": 1.0},
                "rotation": 0.0,
                "transform": {"x": 0.0, "y": 0.0},
                "flip": {"vertical": False, "horizontal": False},
                "alpha": 1.0,
            },
            "uniform_scale": {"on": True, "value": 1.0},
            "extra_material_refs": [],
            "render_index": 0,
            "keyframe_refs": [],
            "enable_lut": True,
            "enable_adjust": True,
            "enable_hsl": False,
            "visible": True,
            "group_id": "",
            "enable_color_curves": True,
            "enable_hsl_curves": True,
            "track_render_index": 0,
            "hdr_settings": {"mode": 1, "intensity": 1.0, "nits": 1000},
            "enable_color_wheels": True,
            "track_attribute": 0,
            "is_placeholder": False,
            "template_id": "",
            "enable_smart_color_adjust": False,
            "template_scene": "default",
            "common_keyframes": [],
            "caption_info": None,
            "responsive_layout": {
                "enable": False, "target_follow": "",
                "size_layout": 0, "horizontal_pos_layout": 0,
                "vertical_pos_layout": 0,
            },
            "enable_color_match_adjust": False,
            "enable_color_correct_adjust": False,
            "enable_adjust_mask": False,
            "raw_segment_id": "",
            "lyric_keyframes": None,
            "enable_video_mask": True,
            "digital_human_template_group_id": "",
            "color_correct_alg_result": "",
            "source": "segmentsourcenormal",
            "enable_mask_stroke": False,
            "enable_mask_shadow": False,
            "enable_color_adjust_pro": False,
        }

    def _make_audio_segment(
        self,
        seg_id: str,
        mat_id: str,
        start_us: int,
        target_dur_us: int,
        source_dur_us: int | None = None,
        volume: float = 1.0,
    ) -> dict:
        """
        target_dur_us  – how long the segment occupies on the CapCut timeline
                         (= trimmed audio duration after silence removal).
        source_dur_us  – how much of the source file to read.  Defaults to
                         target_dur_us when not provided, but should be the exact
                         file duration from ffprobe so the last frame is never
                         clipped by rounding.
        """
        src_dur = source_dur_us if source_dur_us is not None else target_dur_us
        return {
            "id": seg_id,
            "material_id": mat_id,
            "source_timerange": {"start": 0, "duration": src_dur},
            "target_timerange": {"start": start_us, "duration": target_dur_us},
            "render_timerange": {"start": 0, "duration": 0},
            "desc": "",
            "state": 0,
            "speed": 1.0,
            "is_loop": False,
            "is_tone_modify": False,
            "reverse": False,
            "intensifies_audio": False,
            "cartoon": False,
            "volume": volume,
            "last_nonzero_volume": max(volume, 0.01),
            "clip": None,
            "extra_material_refs": [],
            "render_index": 0,
            "keyframe_refs": [],
            "visible": True,
            "group_id": "",
            "track_render_index": 0,
            "hdr_settings": None,
            "track_attribute": 0,
            "is_placeholder": False,
            "template_id": "",
            "template_scene": "default",
            "common_keyframes": [],
            "caption_info": None,
            "raw_segment_id": "",
            "lyric_keyframes": None,
        }

    # ------------------------------------------------------------------ #
    # Track builder
    # ------------------------------------------------------------------ #

    def _make_track(
        self,
        track_id: str,
        track_type: str,
        track_name: str,
        segments: list[dict],
    ) -> dict:
        return {
            "id": track_id,
            "type": track_type,
            "segments": segments,
            "flag": 0,
            "attribute": 0,
            "name": track_name or "",
            "is_default_name": not bool(track_name),
        }

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def _new_uuid(self) -> str:
        return str(uuid.uuid4()).upper()

    def _ms_to_us(self, ms: int) -> int:
        return ms * 1000

    def _frames_to_us(self, frames: int, fps: float) -> int:
        if fps <= 0:
            fps = 30.0
        return int((frames / fps) * 1_000_000)

    def _get_file_duration_us(self, file_path: str) -> int | None:
        """Return the exact duration of a media file in microseconds via ffprobe."""
        try:
            result = subprocess.run(
                [
                    find_ffprobe(), "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json",
                    file_path,
                ],
                capture_output=True, text=True, check=True,
                encoding="utf-8", errors="replace",
            )
            data = json.loads(result.stdout)
            return int(float(data["format"]["duration"]) * 1_000_000)
        except Exception:
            return None
