"""Minimal Qt application startup wiring."""

import sys

from PySide6.QtWidgets import QApplication

from leviathan_clipper.ui.main_window import MainWindow
from leviathan_clipper.application.import_video import ImportService
from leviathan_clipper.video.probe import VideoProbe
from leviathan_clipper.video.ffmpeg import FFmpeg
from leviathan_clipper.transcription.whisper import WhisperTranscriber
from leviathan_clipper.persistence.transcripts import TranscriptStore
from leviathan_clipper.application.transcribe_video import TranscriptionService
from leviathan_clipper.application.providers import ProviderService
from leviathan_clipper.application.analyze_clips import AnalysisService
from leviathan_clipper.analysis.analyzer import ClipAnalyzer
from leviathan_clipper.application.review_clips import ReviewService
from leviathan_clipper.persistence.review_projects import ReviewProjectStore


def main(argv: list[str] | None = None) -> int:
    """Show the application shell and run the Qt event loop."""
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("LeviathanClipper")
    providers = ProviderService()
    window = MainWindow(
        ImportService(VideoProbe()),
        TranscriptionService(FFmpeg(), WhisperTranscriber(), TranscriptStore()),
        providers,
        AnalysisService(ClipAnalyzer(providers)),
        ReviewService(ReviewProjectStore(), VideoProbe()),
    )
    window.show()
    return app.exec()
