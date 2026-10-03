"""Source-time candidates and bounded analysis settings."""

from dataclasses import dataclass
import math


QUALITY_NAMES = ("hook", "context", "humor", "emotion", "conflict", "information", "surprise", "completeness", "ending")


@dataclass(frozen=True)
class AnalysisSettings:
    count: int = 5
    min_duration: float = 20
    max_duration: float = 60
    chunk_bytes: int = 4000
    overlap_seconds: float = 20
    minimum_score: float = 40
    rank_with_llm: bool = False

    def __post_init__(self):
        if (not 1 <= self.count <= 50 or not 1 <= self.min_duration <= self.max_duration <= 600
                or not 512 <= self.chunk_bytes <= 12000 or not 0 <= self.overlap_seconds <= 60
                or not 0 <= self.minimum_score <= 100
                or not all(math.isfinite(v) for v in (self.min_duration, self.max_duration, self.overlap_seconds, self.minimum_score))):
            raise ValueError("Invalid clip count, duration bounds, or analysis budget.")


@dataclass(frozen=True)
class Candidate:
    id: str
    start: float
    end: float
    title: str
    score: float
    reason: str
    text: str
    quality: tuple[int, ...]

    def __post_init__(self):
        if (not self.id or not self.title.strip() or not self.reason.strip()
                or not all(math.isfinite(v) for v in (self.start, self.end, self.score))
                or self.start < 0 or self.end <= self.start or not 0 <= self.score <= 100
                or len(self.quality) != 9 or any(type(v) is not int or not 0 <= v <= 5 for v in self.quality)):
            raise ValueError("Invalid candidate data.")

    @property
    def duration(self):
        return self.end - self.start

    @property
    def selection_score(self):
        # Interesting clips need one strong interest signal, not every possible emotion.
        hook, context, *_, completeness, ending = self.quality
        interest = max(self.quality[2:7])
        quality_score = 4 * (hook + context + interest + completeness + ending)
        return (self.score + quality_score) / 2


@dataclass(frozen=True)
class AnalysisResult:
    candidates: tuple[Candidate, ...]
    suggested_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    requested_count: int

    @property
    def suggested(self):
        lookup = {candidate.id: candidate for candidate in self.candidates}
        return tuple(lookup[id] for id in self.suggested_ids)
