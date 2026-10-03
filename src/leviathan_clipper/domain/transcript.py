"""Provider-independent timestamped transcript data."""

from dataclasses import dataclass
import math
from pathlib import Path


class TranscriptionError(Exception):
    """An actionable transcription or transcript-file error."""


@dataclass(frozen=True)
class TranscriptionSettings:
    model: str = "tiny"
    device: str = "cpu"
    language: str | None = None
    compute_type: str = "int8"

    def __post_init__(self):
        if not self.model.strip():
            raise ValueError("Choose a downloaded Whisper model or a local model folder.")
        if self.device not in {"cpu", "cuda", "auto"}:
            raise ValueError("Device must be cpu, cuda, or auto.")
        if self.compute_type not in {"int8", "float32", "float16", "default"}:
            raise ValueError("Unsupported compute type.")


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str

    def __post_init__(self):
        if (not math.isfinite(self.start) or not math.isfinite(self.end)
                or self.start < 0 or self.end <= self.start
                or not isinstance(self.text, str) or not self.text.strip()):
            raise ValueError("Segments must have finite increasing timestamps and nonempty text.")


@dataclass(frozen=True)
class Transcript:
    source_path: Path
    source_duration: float
    source_size: int
    source_mtime_ns: int
    language: str
    model: str
    segments: tuple[TranscriptSegment, ...]

    def __post_init__(self):
        if (not math.isfinite(self.source_duration) or self.source_duration <= 0
                or self.source_size < 0 or self.source_mtime_ns < 0
                or not self.language or not self.model):
            raise ValueError("Invalid transcript source or model metadata.")
        previous = -1.0
        for segment in self.segments:
            if segment.start < previous or segment.end > self.source_duration:
                raise ValueError("Transcript segments must be ordered and inside the source duration.")
            previous = segment.start
