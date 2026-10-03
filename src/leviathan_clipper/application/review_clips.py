"""Validated edits, approvals and review persistence; no renderer."""

from dataclasses import replace
import math
from leviathan_clipper.analysis.analyzer import transcript_text
from leviathan_clipper.domain.cancellation import check_cancelled
from leviathan_clipper.domain.review import ReviewError, ReviewProject


class ReviewService:
    def __init__(self, store, probe):
        self.store, self.probe = store, probe

    def begin(self, source, transcript, result):
        return ReviewProject(source, transcript, result.candidates, result.suggested_ids)

    def select(self, project, id, selected):
        if id not in {c.id for c in project.candidates}:
            raise ReviewError("Unknown clip selection.")
        ids = set(project.selected_ids)
        ids.add(id) if selected else ids.discard(id)
        return replace(project, selected_ids=tuple(c.id for c in project.candidates if c.id in ids), approved_ids=())

    def edit(self, project, id, start, end):
        if (not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= project.source.duration):
            raise ReviewError("Clip boundaries must satisfy 0 ≤ start < end ≤ source duration.")
        if id not in {c.id for c in project.candidates}:
            raise ReviewError("Unknown clip interval.")
        candidates = tuple(replace(c, start=start, end=end, text=transcript_text(project.transcript, start, end))
                           if c.id == id else c for c in project.candidates)
        return replace(project, candidates=candidates, approved_ids=())

    def approve(self, project):
        if not project.selected_ids:
            raise ReviewError("Select at least one clip before approving.")
        return replace(project, approved_ids=project.selected_ids)

    def approved_selection(self, project):
        if not project.approved_ids or set(project.approved_ids) != set(project.selected_ids):
            raise ReviewError("Approve the current selection before continuing.")
        return project.approved_clips

    def _verify_source(self, project, cancel):
        check_cancelled(cancel)
        try:
            stat = project.source.path.stat()
        except OSError as exc:
            raise ReviewError(f"Review source is missing/unreadable: {exc}") from exc
        if (stat.st_size != project.transcript.source_size or stat.st_mtime_ns != project.transcript.source_mtime_ns):
            raise ReviewError("The source changed since this review. Re-import and analyze it.")

    def save(self, project, path, cancel, progress):
        progress(0, "Saving reviewed clips…")
        self._verify_source(project, cancel)
        result = self.store.save(project, path, cancel)
        progress(1, "Review project saved.")
        return result

    def load(self, path, cancel, progress):
        progress(0, "Loading review project…")
        project = self.store.load(path, cancel)
        self._verify_source(project, cancel)
        actual = self.probe.probe(project.source.path, cancel=cancel)
        if (abs(actual.duration - project.source.duration) > 0.25
                or (actual.width, actual.height, actual.has_audio) !=
                   (project.source.width, project.source.height, project.source.has_audio)):
            raise ReviewError("Saved source metadata no longer matches this video.")
        check_cancelled(cancel)
        progress(1, "Review project loaded.")
        return replace(project, source=actual)
