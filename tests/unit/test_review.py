from dataclasses import replace
import json
from threading import Event

import pytest
from leviathan_clipper.application.review_clips import ReviewService
from leviathan_clipper.domain.cancellation import CancelledError
from leviathan_clipper.domain.clips import AnalysisResult, Candidate
from leviathan_clipper.domain.media import SourceMedia
from leviathan_clipper.domain.review import ReviewError, ReviewProject
from leviathan_clipper.domain.transcript import Transcript, TranscriptSegment
from leviathan_clipper.persistence.review_projects import ReviewProjectStore


@pytest.fixture
def review(tmp_path):
    path = tmp_path / "source.mp4"
    path.write_bytes(b"source remains untouched")
    stat = path.stat()
    source = SourceMedia(path, 60, 160, 90, 25, True)
    transcript = Transcript(path, 60, stat.st_size, stat.st_mtime_ns, "en", "local", (
        TranscriptSegment(0, 20, "A hook and a complete conclusion."),
        TranscriptSegment(20, 40, "A funny second moment."),
        TranscriptSegment(40, 60, "A final explanation."),
    ))
    candidates = tuple(Candidate(str(i), start, end, title, 85, "Clear context and ending", text, (4,) * 9)
                       for i, start, end, title, text in (
                           (1, 0, 20, "First", "A hook and a complete conclusion."),
                           (2, 20, 40, "Second", "A funny second moment.")))
    return ReviewProject(source, transcript, candidates, ("1",))


def service(project):
    class Probe:
        def probe(self, path, cancel):
            assert path == project.source.path
            return project.source
    return ReviewService(ReviewProjectStore(), Probe())


def test_suggestions_are_not_approved_and_handoff_contains_only_selected(review):
    svc = service(review)
    result = AnalysisResult(review.candidates, ("1",), (), 1)
    initial = svc.begin(review.source, review.transcript, result)
    assert initial == review and not initial.approved_clips
    with pytest.raises(ReviewError, match="Approve"):
        svc.approved_selection(initial)
    approved = svc.approve(initial)
    assert svc.approved_selection(approved) == (review.candidates[0],)
    changed = svc.select(approved, "2", True)
    assert changed.selected_ids == ("1", "2") and not changed.approved_clips
    changed = svc.select(changed, "1", False)
    assert svc.approved_selection(svc.approve(changed)) == (review.candidates[1],)
    with pytest.raises(ReviewError, match="at least one"):
        svc.approve(svc.select(changed, "2", False))
    with pytest.raises(ReviewError, match="Unknown"):
        svc.select(changed, "missing", True)


@pytest.mark.parametrize("start,end", [(-1, 20), (20, 20), (30, 20), (0, 61), (float("nan"), 20), (0, float("inf"))])
def test_reject_invalid_intervals_without_mutating_approved_review(review, start, end):
    svc = service(review)
    approved = svc.approve(review)
    with pytest.raises(ReviewError, match="boundaries"):
        svc.edit(approved, "1", start, end)
    assert svc.approved_selection(approved) == (review.candidates[0],)


def test_edit_updates_text_duration_and_revokes_approval(review):
    svc = service(review)
    edited = svc.edit(svc.approve(review), "1", 15, 45)
    assert edited.candidates[0].duration == 30
    assert "second moment" in edited.candidates[0].text and "final explanation" in edited.candidates[0].text
    assert not edited.approved_ids and edited.selected_ids == review.selected_ids
    with pytest.raises(ReviewError, match="Unknown"):
        svc.edit(review, "missing", 0, 10)


def test_saved_selection_edits_and_approvals_survive_reload_without_inference(review, tmp_path):
    svc = service(review)
    edited = svc.edit(review, "1", 1.25, 18.75)
    approved = svc.approve(svc.select(edited, "2", True))
    path = tmp_path / "проект reviewed.json"
    svc.save(approved, path, Event(), lambda *args: None)
    restored = svc.load(path, Event(), lambda *args: None)
    assert restored == approved and svc.approved_selection(restored) == approved.candidates
    assert review.source.path.read_bytes() == b"source remains untouched"
    review.source.path.write_bytes(b"changed source")
    with pytest.raises(ReviewError, match="source changed"):
        svc.load(path, Event(), lambda *args: None)


@pytest.mark.parametrize("change", [
    lambda data: data.update(schema_version=99),
    lambda data: data.update(approved_ids=["2"]),
    lambda data: data.update(selected_ids=["missing"]),
    lambda data: data["candidates"][0].update(end=61),
    lambda data: data["candidates"][0].update(start=-1),
    lambda data: data.update(unexpected=True),
    lambda data: data["candidates"][0].update(quality=[4]),
])
def test_corrupt_project_is_an_actionable_error(review, tmp_path, change):
    store, path = ReviewProjectStore(), tmp_path / "review.json"
    store.save(review, path, Event())
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ReviewError, match="load review"):
        store.load(path, Event())


def test_cancelled_save_and_io_failure_preserve_files(review, tmp_path, monkeypatch):
    store, path = ReviewProjectStore(), tmp_path / "review.json"
    path.write_text("existing review")
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        store.save(review, path, cancel)
    with pytest.raises(ReviewError, match="overwrite"):
        store.save(review, review.source.path, Event())
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr("leviathan_clipper.persistence.review_projects.os.replace", fail)
    with pytest.raises(ReviewError, match="disk unavailable"):
        store.save(review, path, Event())
    assert path.read_text() == "existing review"
    assert not list(tmp_path.glob("leviathan-review-*"))


def test_source_metadata_mismatch_and_missing_source_fail_reload(review, tmp_path):
    svc, path = service(review), tmp_path / "review.json"
    svc.save(review, path, Event(), lambda *a: None)
    svc.probe.probe = lambda *a, **kw: replace(review.source, width=320)
    with pytest.raises(ReviewError, match="metadata"):
        svc.load(path, Event(), lambda *a: None)
    review.source.path.unlink()
    with pytest.raises(ReviewError, match="missing/unreadable"):
        svc.load(path, Event(), lambda *a: None)
