"""Review snapshots distinguish suggested, selected and approved clips."""

from dataclasses import dataclass
import math
from leviathan_clipper.domain.clips import Candidate
from leviathan_clipper.domain.media import SourceMedia
from leviathan_clipper.domain.transcript import Transcript


class ReviewError(Exception):
    """An invalid interval, selection or saved review project."""


@dataclass(frozen=True)
class ReviewProject:
    source: SourceMedia
    transcript: Transcript
    candidates: tuple[Candidate, ...]
    selected_ids: tuple[str, ...]
    approved_ids: tuple[str, ...] = ()

    def __post_init__(self):
        source = self.source
        if (not math.isfinite(source.duration) or source.duration <= 0 or min(source.width, source.height) <= 0
                or (source.frame_rate is not None and (not math.isfinite(source.frame_rate) or source.frame_rate <= 0))
                or source.path.resolve() != self.transcript.source_path.resolve()
                or abs(source.duration - self.transcript.source_duration) > 0.25):
            raise ValueError("Review source and transcript metadata do not match.")
        ids = {candidate.id for candidate in self.candidates}
        if (len(ids) != len(self.candidates) or len(set(self.selected_ids)) != len(self.selected_ids)
                or len(set(self.approved_ids)) != len(self.approved_ids)
                or not set(self.selected_ids) <= ids or not set(self.approved_ids) <= set(self.selected_ids)
                or (self.approved_ids and set(self.approved_ids) != set(self.selected_ids))
                or any(c.end > source.duration for c in self.candidates)):
            raise ValueError("Invalid review candidates, intervals or approvals.")

    @property
    def approved_clips(self):
        approved = set(self.approved_ids)
        return tuple(c for c in self.candidates if c.id in approved)
