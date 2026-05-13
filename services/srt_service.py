import re
from pathlib import Path

from models.subtitle_segment import SubtitleSegment


class SrtService:
    TIME_PATTERN = re.compile(
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
    )

    def parse(self, file_path: Path) -> list[SubtitleSegment]:
        content = file_path.read_text(encoding="utf-8-sig")

        blocks = re.split(r"\n\s*\n", content.strip())
        segments: list[SubtitleSegment] = []

        for block in blocks:
            lines = block.strip().splitlines()

            if len(lines) < 3:
                continue

            try:
                index = int(lines[0].strip())
            except ValueError:
                index = len(segments) + 1

            time_match = self.TIME_PATTERN.search(lines[1])

            if not time_match:
                continue

            start_time = time_match.group(1)
            end_time = time_match.group(2)
            text = "\n".join(lines[2:]).strip()

            segments.append(
                SubtitleSegment(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    original_text=text,
                )
            )

        return segments

    def export(self, segments: list[SubtitleSegment], file_path: Path) -> None:
        lines: list[str] = []

        for segment in segments:
            lines.append(str(segment.index))
            lines.append(f"{segment.start_time} --> {segment.end_time}")
            lines.append(segment.display_text)
            lines.append("")

        file_path.write_text("\n".join(lines), encoding="utf-8")