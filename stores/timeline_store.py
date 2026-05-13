import copy
from dataclasses import dataclass

from models.timeline_cache import TimelineCache
from models.timeline_item import TimelineItem
from models.timeline_track import TimelineTrack


@dataclass
class TimelineSnapshot:
    tracks: list[TimelineTrack]
    items: list[TimelineItem]
    current_frame: int
    fps: float


class TimelineStore:
    def __init__(self, fps: float = 30.0):
        self.tracks: list[TimelineTrack] = []
        self.items: list[TimelineItem] = []

        self.fps = fps
        self.current_frame = 0

        self._undo_stack: list[TimelineSnapshot] = []
        self._redo_stack: list[TimelineSnapshot] = []

        self.max_undo_history = 50

        self._items_by_track_id: dict[str, list[TimelineItem]] = {}
        self._item_by_id: dict[str, TimelineItem] = {}

        self._rebuild_indexes()

    def load_cache(self, cache: TimelineCache):
        self.tracks = copy.deepcopy(cache.tracks)
        self.items = copy.deepcopy(cache.items)
        self.fps = cache.fps
        self.current_frame = 0
        self._rebuild_indexes()

    def to_cache_base(self) -> tuple[list[TimelineTrack], list[TimelineItem]]:
        return copy.deepcopy(self.tracks), copy.deepcopy(self.items)

    def _rebuild_indexes(self):
        self._item_by_id = {
            item.id: item
            for item in self.items
        }

        self._items_by_track_id = {}

        for item in self.items:
            self._items_by_track_id.setdefault(item.track_id, []).append(item)

        for track_id in self._items_by_track_id:
            self._items_by_track_id[track_id].sort(
                key=lambda item: item.from_frame
            )

    def get_items_on_track(self, track_id: str) -> list[TimelineItem]:
        return self._items_by_track_id.get(track_id, [])

    def get_item(self, item_id: str) -> TimelineItem | None:
        return self._item_by_id.get(item_id)

    def get_sorted_tracks(self) -> list[TimelineTrack]:
        return sorted(self.tracks, key=lambda track: track.order)

    def execute(self, action_fn):
        before = self._capture_snapshot()

        action_fn()

        after = self._capture_snapshot()

        if before != after:
            self._undo_stack.append(before)

            if len(self._undo_stack) > self.max_undo_history:
                self._undo_stack.pop(0)

            self._redo_stack.clear()

        self._rebuild_indexes()

    def _capture_snapshot(self) -> TimelineSnapshot:
        return TimelineSnapshot(
            tracks=copy.deepcopy(self.tracks),
            items=copy.deepcopy(self.items),
            current_frame=self.current_frame,
            fps=self.fps,
        )

    def _restore_snapshot(self, snapshot: TimelineSnapshot):
        self.tracks = snapshot.tracks
        self.items = snapshot.items
        self.current_frame = snapshot.current_frame
        self.fps = snapshot.fps
        self._rebuild_indexes()

    def undo(self):
        if not self._undo_stack:
            return

        current = self._capture_snapshot()
        previous = self._undo_stack.pop()

        self._redo_stack.append(current)
        self._restore_snapshot(previous)

    def redo(self):
        if not self._redo_stack:
            return

        current = self._capture_snapshot()
        next_snapshot = self._redo_stack.pop()

        self._undo_stack.append(current)
        self._restore_snapshot(next_snapshot)