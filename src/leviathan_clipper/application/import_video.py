"""Validate metadata before updating the current project."""

import math
from pathlib import Path
from leviathan_clipper.domain.cancellation import check_cancelled
from leviathan_clipper.domain.media import ProjectState, SourceMedia
from leviathan_clipper.video.tools import MediaError


class ImportService:
    def __init__(self, probe, state=None):
        self.probe = probe
        self.state = state if state is not None else ProjectState()

    def inspect(self, path, cancel, progress):
        check_cancelled(cancel)
        progress(0, "Reading video metadata…")
        metadata = self.probe.probe(Path(path), cancel=cancel)
        if (not isinstance(metadata, SourceMedia) or not math.isfinite(metadata.duration)
                or metadata.duration <= 0 or min(metadata.width, metadata.height) <= 0
                or (metadata.frame_rate is not None and
                    (not math.isfinite(metadata.frame_rate) or metadata.frame_rate <= 0))):
            raise MediaError("The selected file has invalid video metadata.")
        check_cancelled(cancel)
        progress(1, "Video imported.")
        return metadata

    def select(self, metadata):
        self.state.source = metadata
