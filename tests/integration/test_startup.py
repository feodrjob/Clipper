"""Exercise real Qt startup and close the window automatically."""

import os
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("launcher", ["module", "gui_entry_point"])
def test_window_launches_and_closes(launcher, tmp_path):
    script = textwrap.dedent("""
        import importlib.metadata
        import runpy
        import sys

        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from leviathan_clipper.ui.main_window import MainWindow

        def forbid_processing(event, args):
            if event in {"subprocess.Popen", "os.system", "socket.connect"}:
                raise AssertionError(f"Unexpected startup activity: {event}")

        sys.addaudithook(forbid_processing)
        observed = []

        def check_and_close():
            app = QApplication.instance()
            windows = [w for w in app.topLevelWidgets() if isinstance(w, MainWindow)]
            assert len(windows) == 1
            window = windows[0]
            assert window.isVisible()
            assert window.windowTitle() == "LeviathanClipper"
            assert window.title.text() == "LeviathanClipper"
            assert window.import_button.isEnabled()
            assert window.import_service.state.source is None
            assert window.worker is None
            assert not any(
                name.split(".")[0] in {"faster_whisper", "ollama", "cv2", "mediapipe"}
                for name in sys.modules
            )
            observed.append(window.close())

        original_show = MainWindow.show

        def show_and_schedule_close(self):
            original_show(self)
            QTimer.singleShot(250, check_and_close)
            # A failed callback must not leave a hung event loop.
            QTimer.singleShot(5000, lambda: QApplication.instance().exit(99))

        MainWindow.show = show_and_schedule_close
        if sys.argv[1] == "module":
            try:
                runpy.run_module("leviathan_clipper", run_name="__main__")
            except SystemExit as exc:
                assert exc.code == 0
        else:
            entries = importlib.metadata.distribution("leviathan-clipper").entry_points
            entry, = [e for e in entries if e.group == "gui_scripts" and e.name == "leviathan-clipper"]
            assert entry.load()() == 0
        assert observed == [True], "Window was not inspected and closed successfully"
        assert not any(w.isVisible() for w in QApplication.instance().topLevelWidgets())
    """)
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, launcher],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
