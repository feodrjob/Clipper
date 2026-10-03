from threading import Event, get_ident
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from leviathan_clipper.application.import_video import ImportService
from leviathan_clipper.domain.media import SourceMedia
from leviathan_clipper.ui.main_window import MainWindow
from leviathan_clipper.video.probe import VideoProbe
from leviathan_clipper.video.tools import MediaError


def test_import_ui_background_error_cancel_and_close(qapp, wait_for, tmp_path, monkeypatch):
    main_thread = get_ident()
    worker_threads = []
    media = SourceMedia(tmp_path / "selected.mp4", 2, 160, 90, 25, True)

    def slow_probe(path, cancel):
        worker_threads.append(get_ident())
        cancel.wait(0.1)
        if path.name == "invalid":
            raise MediaError("Invalid test video")
        return media

    service = ImportService(SimpleNamespace(probe=slow_probe))
    window = MainWindow(service)
    window.show()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(media.path), ""))
    heartbeats = []
    timer = QTimer()
    timer.timeout.connect(lambda: heartbeats.append(True))
    timer.start(10)
    try:
        window.import_button.click()
        wait_for(lambda: window.worker is None)
        assert service.state.source is media
        assert str(media.path) in window.metadata.text()
        assert "160 × 90" in window.metadata.text() and "Audio: Yes" in window.metadata.text()
        assert heartbeats and all(t != main_thread for t in worker_threads)
        window.import_video("invalid")
        wait_for(lambda: window.worker is None)
        assert "Invalid test video" in window.status.text()
        assert service.state.source is media
        window.import_video("cancel")
        window.cancel_button.click()
        wait_for(lambda: window.worker is None)
        assert "cancelled" in window.status.text() and service.state.source is media
        window.import_video("close")
        window.close()
        wait_for(lambda: window.worker is None)
        assert not window.isVisible()
    finally:
        timer.stop()
        if window.worker is not None:
            window.cancel_task()
            wait_for(lambda: window.worker is None)
        window.close()


def test_real_file_dialog_selection(qapp, wait_for, video_fixture, tools, monkeypatch):
    service = ImportService(VideoProbe(tools))
    window = MainWindow(service)
    window.show()
    original = QFileDialog.getOpenFileName
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda parent, title, directory, filters: original(
        parent, title, str(video_fixture.parent), filters,
        options=QFileDialog.Option.DontUseNativeDialog,
    ))
    chosen = []

    def select_file():
        for widget in qapp.topLevelWidgets():
            if isinstance(widget, QFileDialog):
                from PySide6.QtWidgets import QLineEdit
                widget.findChild(QLineEdit, "fileNameEdit").setText(video_fixture.name)
                chosen.append(True)
                widget.accept()

    QTimer.singleShot(500, select_file)
    def reject_stalled_dialog():
        for widget in qapp.topLevelWidgets():
            if isinstance(widget, QFileDialog) and widget.isVisible():
                widget.reject()
    QTimer.singleShot(3000, reject_stalled_dialog)
    try:
        window.import_button.click()
        wait_for(lambda: window.worker is None)
        assert chosen and service.state.source.path == video_fixture
    finally:
        if window.worker is not None:
            window.cancel_task()
            wait_for(lambda: window.worker is None)
        window.close()
