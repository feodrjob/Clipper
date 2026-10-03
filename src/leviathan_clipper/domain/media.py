"""Source metadata, independent of Qt and media tools."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceMedia:
    path: Path
    duration: float
    width: int
    height: int
    frame_rate: float | None
    has_audio: bool


@dataclass
class ProjectState:
    source: SourceMedia | None = None
