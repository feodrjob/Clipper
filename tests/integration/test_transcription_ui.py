from threading import get_ident
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from leviathan_clipper.application.import_video import ImportService
from leviathan_clipper.application.transcribe_video import TranscriptionService
from leviathan_clipper.domain.transcript import TranscriptSegment, TranscriptionError
from leviathan_clipper.persistence.transcripts import TranscriptStore
from leviathan_clipper.ui.main_window import MainWindow
from leviathan_clipper.video.ffmpeg import FFmpeg
from leviathan_clipper.video.probe import VideoProbe


def test_extraction_preserves_delayed_audio_timeline(tools, tmp_path):
    import struct
    import subprocess
    from threading import Event
    import wave
    from leviathan_clipper.domain.transcript import TranscriptionSettings
    path = tmp_path / "delayed.mp4"
    subprocess.run([
        tools.resolve("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=blue:s=160x90:r=25:d=3",
        "-itsoffset", "1", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=1",
        "-c:v", "mpeg4", "-c:a", "aac", str(path),
    ], check=True, capture_output=True, timeout=20)
    def inspect_audio(audio, settings, duration, cancel, progress):
        with wave.open(str(audio), "rb") as wav:
            assert wav.getframerate() == 16000 and wav.getnchannels() == 1
            silence = wav.readframes(12000)
            assert max(abs(sample) for sample in struct.unpack(f"<{len(silence)//2}h", silence)) < 50
            sound = wav.readframes(16000)
            assert max(abs(sample) for sample in struct.unpack(f"<{len(sound)//2}h", sound)) > 100
        return "en", (TranscriptSegment(1, 2, "delayed speech"),)
    service = TranscriptionService(FFmpeg(tools), SimpleNamespace(transcribe=inspect_audio), TranscriptStore())
    result = service.generate(VideoProbe(tools).probe(path), TranscriptionSettings(), Event(), lambda *a: None)
    assert result.segments[0].start == 1


def test_gui_transcribe_save_load_cancel_error_and_responsiveness(qapp, wait_for, video_fixture, tools, tmp_path, monkeypatch):
    threads, ticks, mode = [], [], ["normal"]
    def fake_transcribe(audio, settings, duration, cancel, progress):
        threads.append(get_ident())
        cancel.wait(0.1)
        if mode[0] == "fail":
            raise TranscriptionError("Missing model test")
        return "en", (TranscriptSegment(0, 1, "Hello local world"),)
    service = TranscriptionService(FFmpeg(tools), SimpleNamespace(transcribe=fake_transcribe), TranscriptStore())
    window = MainWindow(ImportService(VideoProbe(tools)), service)
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(10)
    window.show()
    try:
        assert not window.transcribe_button.isEnabled()
        window.import_video(video_fixture)
        wait_for(lambda: window.worker is None)
        assert window.transcribe_button.isEnabled()
        window.transcribe_button.click()
        wait_for(lambda: window.worker is None)
        original = window.transcript
        assert ticks and all(t != get_ident() for t in threads)
        assert "Hello local world" in window.transcript_view.toPlainText()
        path = tmp_path / "saved.json"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(path), ""))
        window.save_button.click()
        wait_for(lambda: window.worker is None)
        assert path.is_file()
        mode[0] = "fail"
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(path), ""))
        window.load_button.click()
        wait_for(lambda: window.worker is None)
        assert window.transcript == original and len(threads) == 1
        window.transcribe_button.click()
        wait_for(lambda: window.worker is None)
        assert "Missing model" in window.status.text() and window.transcript == original
        mode[0] = "normal"
        window.transcribe_button.click()
        window.cancel_button.click()
        wait_for(lambda: window.worker is None)
        assert "cancelled" in window.status.text() and window.transcript == original
        window.import_video(video_fixture)
        wait_for(lambda: window.worker is None)
        assert window.transcript is None and not window.save_button.isEnabled()
    finally:
        timer.stop()
        if window.worker is not None:
            window.cancel_task()
            wait_for(lambda: window.worker is None)
        window.close()
