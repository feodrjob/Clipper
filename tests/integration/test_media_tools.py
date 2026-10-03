import hashlib
from pathlib import Path
import sys
from threading import Event, Timer

import pytest
from leviathan_clipper.application.import_video import ImportService
from leviathan_clipper.domain.cancellation import CancelledError
from leviathan_clipper.video.ffmpeg import FFmpeg
from leviathan_clipper.video.probe import VideoProbe
from leviathan_clipper.video.tools import MediaError, ProcessRunner


def test_real_probe_import_and_transcode(video_fixture, tools, tmp_path):
    original_hash = hashlib.sha256(video_fixture.read_bytes()).digest()
    service = ImportService(VideoProbe(tools))
    media = service.inspect(video_fixture, Event(), lambda *a: None)
    service.select(media)
    assert service.state.source.path == video_fixture
    assert (media.width, media.height, media.frame_rate, media.has_audio) == (160, 90, 25, True)
    assert media.duration == pytest.approx(2, abs=0.1)
    progress = []
    output = tmp_path / "new output.mp4"
    FFmpeg(tools).transcode(video_fixture, output, ["-c:v", "mpeg4", "-c:a", "aac"], progress=progress.append)
    assert VideoProbe(tools).probe(output).duration == pytest.approx(2, abs=0.1)
    assert progress and max(progress) > 0
    assert hashlib.sha256(video_fixture.read_bytes()).digest() == original_hash
    bad = tmp_path / "broken.mp4"
    bad.write_text("not video")
    with pytest.raises(MediaError):
        service.inspect(bad, Event(), lambda *a: None)
    assert service.state.source is media


def test_real_ffmpeg_failure_and_cancellation_cleanup(video_fixture, tools, tmp_path):
    ffmpeg = FFmpeg(tools)
    output = tmp_path / "failed.mp4"
    with pytest.raises(MediaError, match="failed"):
        ffmpeg.transcode(video_fixture, output, ["-c:v", "not_an_encoder"])
    assert not output.exists()
    cancel = Event()

    def stop(seconds):
        cancel.set()

    with pytest.raises(CancelledError):
        ffmpeg.transcode(video_fixture, output, ["-c:v", "mpeg4"], cancel=cancel, progress=stop)
    assert not output.exists() and not list(tmp_path.glob("leviathan-*"))


def test_runner_failure_timeout_cancel_and_large_stderr():
    runner = ProcessRunner()
    with pytest.raises(MediaError, match="exit 3.*"):
        runner.run([sys.executable, "-c", "import sys; print('failure', file=sys.stderr); sys.exit(3)"])
    with pytest.raises(MediaError, match="timed out"):
        runner.run([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)
    cancel = Event()
    timer = Timer(0.15, cancel.set)
    timer.start()
    try:
        with pytest.raises(CancelledError):
            runner.run([sys.executable, "-c", "import time; time.sleep(10)"], cancel=cancel)
    finally:
        timer.join()
    assert runner.run([sys.executable, "-c", "import sys; sys.stderr.write('x'*100000); print('ok')"]).strip() == "ok"
    with pytest.raises(MediaError, match="Could not start"):
        runner.run(["nonexistent-leviathan-tool"])


def test_cancel_running_ffmpeg_reaps_process(video_fixture, tools, monkeypatch):
    import subprocess
    import time
    launched = []
    real_popen = subprocess.Popen

    def record_process(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", record_process)
    cancel = Event()
    timer = Timer(0.3, cancel.set)
    started = time.monotonic()
    timer.start()
    try:
        with pytest.raises(CancelledError):
            ProcessRunner().run([
                tools.resolve("ffmpeg"), "-v", "error", "-nostdin", "-re", "-i",
                str(video_fixture), "-f", "null", "-",
            ], cancel=cancel)
    finally:
        timer.join()
    assert time.monotonic() - started < 2
    assert launched and launched[0].poll() is not None
