"""FFprobe metadata normalization."""

from fractions import Fraction
import json
import math
from pathlib import Path
from leviathan_clipper.domain.media import SourceMedia
from leviathan_clipper.video.tools import MediaError, ProcessRunner, ToolPaths


def parse_metadata(path: Path, payload: str) -> SourceMedia:
    try:
        data = json.loads(payload)
        streams = data["streams"]
        videos = [s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic", 0)]
        if not videos:
            raise ValueError("No playable video stream.")
        video = next((s for s in videos if s.get("disposition", {}).get("default")), videos[0])
        duration = float(data.get("format", {}).get("duration", video.get("duration", 0)))
        width, height = int(video["width"]), int(video["height"])
        if not math.isfinite(duration) or duration <= 0 or min(width, height) <= 0:
            raise ValueError("Invalid video duration or dimensions.")
        rate = None
        for key in ("avg_frame_rate", "r_frame_rate"):
            try:
                value = float(Fraction(video.get(key, "0/0")))
                if math.isfinite(value) and value > 0:
                    rate = value
                    break
            except (ValueError, ZeroDivisionError, TypeError):
                continue
        return SourceMedia(path, duration, width, height, rate,
                           any(s.get("codec_type") == "audio" for s in streams))
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise MediaError(f"Unsupported or invalid video metadata: {exc}") from exc


class VideoProbe:
    def __init__(self, tools=None, runner=None):
        self.tools = tools or ToolPaths()
        self.runner = runner or ProcessRunner()

    def probe(self, path, cancel=None):
        path = Path(path).resolve()
        if not path.is_file():
            raise MediaError(f"Video file does not exist: {path}")
        try:
            with path.open("rb"):
                pass
        except OSError as exc:
            raise MediaError(f"Video file cannot be read: {path}: {exc}") from exc
        payload = self.runner.run([
            self.tools.resolve("ffprobe"), "-v", "error", "-show_format", "-show_streams",
            "-of", "json", "-protocol_whitelist", "file,pipe", str(path),
        ], cancel=cancel, timeout=30)
        return parse_metadata(path, payload)
