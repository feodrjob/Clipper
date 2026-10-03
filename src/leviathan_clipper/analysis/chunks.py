"""UTF-8 bounded transcript chunks with overlap and original timestamp references."""

from dataclasses import dataclass
import json


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class TranscriptRow:
    id: int
    start: float
    end: float
    text: str

    def line(self):
        return compact([self.id, self.start, self.end, self.text])


@dataclass(frozen=True)
class TranscriptChunk:
    rows: tuple[TranscriptRow, ...]

    @property
    def text(self):
        return "\n".join(row.line() for row in self.rows)

    @property
    def ids(self):
        return sorted({row.id for row in self.rows})


def chunk_transcript(transcript, byte_budget, overlap_seconds=20):
    rows = []
    for id, segment in enumerate(transcript.segments):
        text = segment.text
        # A pathological giant segment is split as text; its source boundaries are never invented.
        while text:
            low, high = 1, len(text)
            fit = 0
            while low <= high:
                middle = (low + high) // 2
                row = TranscriptRow(id, segment.start, segment.end, text[:middle])
                if len(row.line().encode("utf-8")) + 1 <= byte_budget:
                    fit, low = middle, middle + 1
                else:
                    high = middle - 1
            if not fit:
                raise ValueError("The transcript chunk budget is too small for timestamped text.")
            rows.append(TranscriptRow(id, segment.start, segment.end, text[:fit]))
            text = text[fit:]
    chunks = []
    start = 0
    while start < len(rows):
        end, used = start, 0
        while end < len(rows) and end - start < 24:
            size = len(rows[end].line().encode("utf-8")) + 1
            if used + size > byte_budget:
                break
            used += size
            end += 1
        chunks.append(TranscriptChunk(tuple(rows[start:end])))
        if end == len(rows):
            break
        next_start, overlap_size = end, 0
        threshold = rows[end - 1].end - overlap_seconds
        while next_start > start + 1 and overlap_seconds > 0:
            prior = rows[next_start - 1]
            size = len(prior.line().encode("utf-8")) + 1
            if prior.end <= threshold or overlap_size + size > byte_budget // 3:
                break
            next_start -= 1
            overlap_size += size
        start = next_start
    return tuple(chunks)
