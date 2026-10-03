from threading import get_ident
import time

from PySide6.QtCore import QTimer
from leviathan_clipper.application.import_video import ImportService
from leviathan_clipper.application.providers import ProviderService
from leviathan_clipper.llm.providers.fake import FakeProvider
from leviathan_clipper.ui.main_window import MainWindow


def test_configured_provider_connection_uses_worker_and_fake_without_gui_changes(qapp, wait_for):
    main_thread = get_ident()
    threads, ticks = [], []
    def respond(request):
        threads.append(get_ident())
        time.sleep(0.08)
        return '{"status":"ok"}'
    provider = FakeProvider([respond, "not JSON"])
    service = ProviderService({"test-provider": lambda config: provider})
    window = MainWindow(ImportService(None), provider_service=service)
    panel = window.provider_panel
    panel.provider.setCurrentText("test-provider")
    panel.model.setText("arbitrary-model")
    panel.endpoint.setText("http://localhost:12345")
    window.pages.setCurrentWidget(panel)
    window.show()
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(10)
    try:
        panel.test_button.click()
        wait_for(lambda: window.worker is None)
        assert "verified" in window.status.text()
        assert ticks and threads[0] != main_thread
        panel.test_button.click()
        wait_for(lambda: window.worker is None)
        assert "invalid JSON" in window.status.text()
        panel.model.clear()
        panel.test_button.click()
        assert "model name" in window.status.text() and window.worker is None
    finally:
        timer.stop()
        if window.worker is not None:
            window.cancel_task()
            wait_for(lambda: window.worker is None)
        window.close()
