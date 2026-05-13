from models.timeline_item import TimelineItem
from models.timeline_track import TimelineTrack
from stores.timeline_store import TimelineStore


class TimelineActions:
    def __init__(self, store: TimelineStore):
        self.store = store

    def add_track(self, track: TimelineTrack):
        def action():
            self.store.tracks.append(track)

        self.store.execute(action)

    def add_item(self, item: TimelineItem):
        def action():
            self.store.items.append(item)

        self.store.execute(action)

    def move_item(self, item_id: str, new_from_frame: int):
        def action():
            item = self.store.get_item(item_id)

            if item is None:
                return

            item.from_frame = max(0, new_from_frame)

        self.store.execute(action)

    def set_track_muted(self, track_id: str, muted: bool):
        def action():
            for track in self.store.tracks:
                if track.id == track_id:
                    track.muted = muted
                    return

        self.store.execute(action)

    def set_item_volume(self, item_id: str, volume: float):
        def action():
            item = self.store.get_item(item_id)

            if item is None:
                return

            item.volume = max(0.0, min(volume, 2.0))

        self.store.execute(action)

    def undo(self):
        self.store.undo()

    def redo(self):
        self.store.redo()