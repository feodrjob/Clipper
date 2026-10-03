from dataclasses import replace
import json
from threading import Event

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QFileDialog
from leviathan_clipper.application.import_video import ImportService
from leviathan_clipper.analysis.analyzer import ClipAnalyzer
from leviathan_clipper.application.analyze_clips import AnalysisService
from leviathan_clipper.application.providers import ProviderService
from leviathan_clipper.application.review_clips import ReviewService
from leviathan_clipper.domain.clips import AnalysisResult, Candidate
from leviathan_clipper.domain.review import ReviewProject
from leviathan_clipper.domain.transcript import Transcript, TranscriptSegment
from leviathan_clipper.persistence.review_projects import ReviewProjectStore
from leviathan_clipper.llm.providers.fake import FakeProvider
from leviathan_clipper.ui.main_window import MainWindow
from leviathan_clipper.video.probe import VideoProbe


@pytest.fixture
def project(video_fixture, tools):
    source = VideoProbe(tools).probe(video_fixture)
    stat = video_fixture.stat()
    transcript = Transcript(video_fixture, source.duration, stat.st_size, stat.st_mtime_ns, "en", "local", (
        TranscriptSegment(0, 1, "A hook and a complete first moment."),
        TranscriptSegment(1, 2, "A funny second moment with its own conclusion."),
    ))
    candidates = tuple(Candidate(str(i), start, end, title, 85, "Strong hook and finished ending", text, (4,) * 9)
                       for i, start, end, title, text in (
                           (1, 0.2, 0.9, "First moment", transcript.segments[0].text),
                           (2, 1, 1.8, "Second moment", transcript.segments[1].text)))
    return ReviewProject(source, transcript, candidates, ("1",))


def make_window(project, tools):
    service = ReviewService(ReviewProjectStore(), VideoProbe(tools))
    window = MainWindow(ImportService(VideoProbe(tools)), review_service=service)
    window._imported(project.source)
    window._transcribed(project.transcript)
    window._set_review(project)
    window.pages.setCurrentWidget(window.review_panel)
    window.show()
    return window


def test_review_controls_edits_approval_save_reload_and_reset(qapp, wait_for, project, tools, tmp_path, monkeypatch):
    window = make_window(project, tools)
    panel = window.review_panel
    timer, ticks = QTimer(), []
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(5)
    try:
        assert panel.table.rowCount() == 2 and not window.approved_clips
        assert panel.table.item(0, 1).text() == "0.20" and panel.table.item(0, 2).text() == "0.90"
        assert "Strong hook" in panel.details.toPlainText() and "85/100" in panel.details.toPlainText()
        panel.approve_button.click()
        assert tuple(c.id for c in window.approved_clips) == ("1",)
        panel.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        assert window.review_project.selected_ids == ("1", "2") and not window.approved_clips
        panel.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
        panel.table.setCurrentCell(1, 0)
        panel.start_field.setValue(1.2)
        panel.end_field.setValue(1.7)
        panel.apply_button.click()
        assert panel.duration_label.text() == "Duration: 0.50 s" and panel.table.item(1, 3).text() == "0.50"
        before = window.review_project
        panel.start_field.setValue(1.9)
        panel.end_field.setValue(1)
        panel.apply_button.click()
        assert window.review_project is before and "boundaries" in window.status.text()
        panel.set_project(before)
        panel.approve_button.click()
        assert tuple(c.id for c in window.approved_clips) == ("2",)
        path = tmp_path / "reviewed.json"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(path), ""))
        panel.save_button.click()
        assert not panel.isEnabled()
        wait_for(lambda: window.worker is None)
        assert path.exists() and "saved" in window.status.text()
        saved = window.review_project
        window._imported(project.source)
        assert window.review_project is None and not window.approved_clips
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **kw: (str(path), ""))
        panel.load_button.click()
        wait_for(lambda: window.worker is None)
        assert window.review_project == saved and window.transcript == project.transcript
        assert window.approved_clips == (saved.candidates[1],) and ticks
        assert panel.table.item(1, 0).checkState() == Qt.CheckState.Checked
        assert panel.table.item(0, 0).checkState() == Qt.CheckState.Unchecked
        assert "1 selected · 1 approved" == panel.summary.text()
        window._transcribed(project.transcript)
        assert not panel.table.rowCount() and not window.approved_clips
    finally:
        timer.stop()
        if window.worker is not None:
            window.cancel_task()
            wait_for(lambda: window.worker is None)
        window.close()


def test_source_interval_preview_frames_stop_replay_and_error(qapp, wait_for, project, tools, tmp_path):
    window = make_window(project, tools)
    panel, frames, positions, ended, errors, ticks = window.review_panel, [], [], [], [], []
    preview = panel.preview
    preview.audio.setMuted(True)
    panel.video.videoSink().videoFrameChanged.connect(lambda frame: frames.append(frame.startTime()) if frame.isValid() else None)
    preview.position.connect(positions.append)
    preview.finished.connect(lambda: ended.append(True))
    preview.failed.connect(errors.append)
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(10)
    original = project.source.path.read_bytes()
    try:
        panel.play_button.click()
        wait_for(lambda: bool(ended) or bool(errors))
        assert not errors and frames and ticks
        assert preview.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
        assert 0.9 <= preview.player.position() / 1000 <= 1.15
        assert any(0.2 <= p <= 0.9 for p in positions)
        assert any(150000 <= t < 900000 for t in frames)
        panel.table.setCurrentCell(1, 0)
        panel.play_button.click()
        wait_for(lambda: len(ended) == 2 or bool(errors))
        assert not errors and 1.8 <= preview.player.position() / 1000 <= 2
        panel.play_button.click()
        panel.stop_button.click()
        assert not preview._pending and not preview._active and not preview.timer.isActive()
        preview.play(project.source, -1, 1)
        assert "outside" in errors[-1]
        preview.play(replace(project.source, path=tmp_path / "missing.mp4"), 0, 1)
        wait_for(lambda: len(errors) >= 2)
        assert "Cannot preview" in window.status.text()
        assert original == project.source.path.read_bytes()
    finally:
        timer.stop()
        window.close()


def test_analysis_enters_review_with_unapproved_suggestions(qapp, wait_for, project, tools):
    fake = FakeProvider([json.dumps({"candidates": [{"first": 0, "last": 1, "title": "Complete moment", "score": 90,
                        "reason": "Clear context and conclusion", "quality": [5, 5, 4, 3, 0, 4, 3, 5, 5]}]})])
    providers = ProviderService({"test": lambda config: fake})
    window = MainWindow(ImportService(VideoProbe(tools)), provider_service=providers,
                        analysis_service=AnalysisService(ClipAnalyzer(providers)),
                        review_service=ReviewService(ReviewProjectStore(), VideoProbe(tools)))
    window._imported(project.source)
    window._transcribed(project.transcript)
    window.provider_panel.provider.setCurrentText("test")
    window.provider_panel.model.setText("arbitrary-local-model")
    window.analysis_panel.minimum.setValue(1)
    window.analysis_panel.maximum.setValue(2)
    window.analysis_panel.count.setValue(1)
    window._update_controls()
    window.show()
    try:
        window.analysis_panel.button.click()
        wait_for(lambda: window.worker is None)
        assert window.review_project.selected_ids == ("clip-0-1",)
        assert window.pages.currentWidget() is window.review_panel
        assert not window.approved_clips and not window.review_project.approved_ids
        window.review_panel.approve_button.click()
        assert window.approved_clips == window.analysis_result.suggested
    finally:
        if window.worker is not None:
            window.cancel_task()
            wait_for(lambda: window.worker is None)
        window.close()
