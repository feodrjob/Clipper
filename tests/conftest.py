"""Small generated media and Qt event-loop helpers."""

import os
from pathlib import Path
import subprocess
import time

import pytest
from leviathan_clipper.video.tools import MediaError, ToolPaths


def pytest_addoption(parser):
    parser.addoption("--run-local-model", action="store_true", help="Run provisioned local Whisper smoke tests")
    parser.addoption("--run-ollama", action="store_true", help="Run an already provisioned Ollama model smoke check")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-local-model"):
        for item in items:
            if "local_model" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Opt-in: use --run-local-model with local model/speech paths"))
    if not config.getoption("--run-ollama"):
        for item in items:
            if "ollama_model" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Opt-in: use --run-ollama with a configured local model"))


@pytest.fixture(scope="session")
def tools():
    root = Path(__file__).resolve().parents[1]
    bins = sorted((root / ".tools" / "ffmpeg").glob("*/bin"))
    paths = ToolPaths(
        os.environ.get("LEVIATHAN_FFMPEG") or (str(bins[-1] / "ffmpeg.exe") if bins else None),
        os.environ.get("LEVIATHAN_FFPROBE") or (str(bins[-1] / "ffprobe.exe") if bins else None),
    )
    try:
        paths.resolve("ffmpeg")
        paths.resolve("ffprobe")
    except MediaError as exc:
        pytest.skip(str(exc))
    return paths


@pytest.fixture
def video_fixture(tmp_path, tools):
    path = tmp_path / "тест source with spaces.mp4"
    subprocess.run([
        tools.resolve("ffmpeg"), "-v", "error", "-nostdin", "-f", "lavfi",
        "-i", "color=c=blue:s=160x90:r=25:d=2", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=16000:duration=2", "-c:v", "mpeg4",
        "-c:a", "aac", "-shortest", str(path),
    ], check=True, capture_output=True, timeout=20)
    return path


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def wait_for(qapp):
    from PySide6.QtTest import QTest

    def wait(predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        assert predicate(), "Timed out waiting for the background operation"

    return wait
