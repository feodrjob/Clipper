import json
from pathlib import Path
from threading import get_ident
import time

from PySide6.QtCore import QTimer
from leviathan_clipper.analysis.analyzer import ClipAnalyzer
from leviathan_clipper.application.analyze_clips import AnalysisService
from leviathan_clipper.application.import_video import ImportService
from leviathan_clipper.application.providers import ProviderService
from leviathan_clipper.domain.transcript import Transcript, TranscriptSegment
from leviathan_clipper.llm.providers.fake import FakeProvider
from leviathan_clipper.ui.main_window import MainWindow


def test_gui_analysis_with_fake_errors_cancellation_and_reset(qapp, wait_for):
    threads, ticks = [], []
    def response(request):
        threads.append(get_ident())
        time.sleep(0.1)
        return json.dumps({"candidates": [{"first": 0, "last": 1, "title": "Complete moment", "score": 90,
                            "reason": "Hook and a complete lesson", "quality": [5, 5, 0, 3, 0, 5, 3, 5, 5]}]})
    provider = FakeProvider([response, "bad", "still bad", response])
    providers = ProviderService({"test": lambda config: provider})
    window = MainWindow(ImportService(None), provider_service=providers, analysis_service=AnalysisService(ClipAnalyzer(providers)))
    window.provider_panel.provider.setCurrentText("test")
    window.provider_panel.model.setText("any-model")
    source = Transcript(Path("video.mp4"), 30, 1, 1, "en", "whisper", (
        TranscriptSegment(0, 10, "A strong opening"), TranscriptSegment(10, 25, "Here is the answer and conclusion"),
    ))
    window._transcribed(source)
    window._update_controls()
    panel = window.analysis_panel
    panel.count.setValue(1)
    window.pages.setCurrentWidget(panel)
    window.show()
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(10)
    try:
        assert panel.button.isEnabled()
        panel.button.click()
        wait_for(lambda: window.worker is None)
        assert window.analysis_result.suggested_ids == ("clip-0-1",)
        assert "Complete moment" in panel.summary.toPlainText()
        assert ticks and threads[0] != get_ident()
        panel.button.click()
        wait_for(lambda: window.worker is None)
        assert not window.analysis_result.candidates and "repair" in panel.summary.toPlainText()
        previous = window.analysis_result
        panel.button.click()
        window.cancel_button.click()
        wait_for(lambda: window.worker is None)
        assert "cancelled" in window.status.text() and window.analysis_result is previous
        window._transcribed(source)
        assert window.analysis_result is None and not panel.summary.toPlainText()
    finally:
        timer.stop()
        if window.worker is not None:
            window.cancel_task()
            wait_for(lambda: window.worker is None)
        window.close()
