import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from leviathan_clipper.application.import_video import ImportService
from leviathan_clipper.domain.cancellation import CancelledError
from leviathan_clipper.domain.media import SourceMedia
from leviathan_clipper.video.ffmpeg import FFmpeg
from leviathan_clipper.video.probe import VideoProbe, parse_metadata
from leviathan_clipper.video.tools import MediaError, ToolPaths


def payload(**video):
    stream = dict(codec_type="video", width=1920, height=1080, avg_frame_rate="30000/1001")
    stream.update(video)
    return json.dumps({"format": {"duration": "120.5"}, "streams": [stream, {"codec_type": "audio"}]})


def test_probe_normalizes_metadata_and_rate_fallback():
    media = parse_metadata(Path("sample.mp4"), payload(avg_frame_rate="0/0", r_frame_rate="25/1"))
    assert (media.duration, media.width, media.height, media.frame_rate, media.has_audio) == (
        120.5, 1920, 1080, 25, True,
    )
    assert parse_metadata(Path("x"), payload()).frame_rate == pytest.approx(29.97002997)


@pytest.mark.parametrize("data", ["invalid", "{}", "null", payload(width=0),
    json.dumps({"streams": [{"codec_type": "audio"}]}),
    json.dumps({"format": {"duration": "NaN"}, "streams": [{"codec_type": "video"}]}),
    payload(disposition={"attached_pic": 1}),
])
def test_invalid_metadata_is_rejected(data):
    with pytest.raises(MediaError, match="metadata"):
        parse_metadata(Path("bad"), data)


def test_discovery_config_environment_path_and_missing(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("shutil.which", lambda name: calls.append(name) or str(tmp_path / "tool.exe"))
    monkeypatch.setenv("LEVIATHAN_FFPROBE", "configured probe")
    ToolPaths(ffprobe="explicit").resolve("ffprobe")
    ToolPaths().resolve("ffprobe")
    monkeypatch.delenv("LEVIATHAN_FFPROBE")
    ToolPaths().resolve("ffprobe")
    assert calls == ["explicit", "configured probe", "ffprobe"]
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(MediaError, match="LEVIATHAN_FFPROBE"):
        ToolPaths().resolve("ffprobe")


def test_probe_missing_unreadable_and_command_failure(tmp_path, monkeypatch):
    with pytest.raises(MediaError, match="does not exist"):
        VideoProbe().probe(tmp_path / "missing")
    path = tmp_path / "video"
    path.write_bytes(b"source")
    probe = VideoProbe(SimpleNamespace(resolve=lambda name: name), SimpleNamespace(
        run=lambda *a, **kw: payload(),
    ))
    assert probe.probe(path).path == path
    monkeypatch.setattr(Path, "open", lambda *a, **kw: (_ for _ in ()).throw(PermissionError("denied")))
    with pytest.raises(MediaError, match="cannot be read"):
        probe.probe(path)


def test_import_commits_only_valid_success_and_preserves_previous(tmp_path):
    original = SourceMedia(tmp_path / "old", 2, 160, 90, 25, True)
    current = SourceMedia(tmp_path / "new", 4, 320, 180, 30, False)
    service = ImportService(SimpleNamespace(probe=lambda *a, **kw: current))
    service.select(original)
    result = service.inspect(current.path, Event(), lambda *a: None)
    assert service.state.source is original
    service.select(result)
    assert service.state.source is current
    service.probe.probe = lambda *a, **kw: SourceMedia(tmp_path / "bad", -1, 0, 0, 0, False)
    with pytest.raises(MediaError):
        service.inspect("bad", Event(), lambda *a: None)
    assert service.state.source is current
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        service.inspect("x", cancel, lambda *a: None)
    assert service.state.source is current


@pytest.mark.parametrize("failure", [MediaError("encoder failed"), CancelledError("cancelled")])
def test_failed_outputs_clean_only_owned_temp_files(tmp_path, failure):
    source, destination = tmp_path / "source.mp4", tmp_path / "output.mp4"
    source.write_bytes(b"original")
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("keep")

    def fail(args, **kwargs):
        Path(args[-1]).write_bytes(b"partial")
        raise failure

    ffmpeg = FFmpeg(SimpleNamespace(resolve=lambda name: name), SimpleNamespace(run=fail))
    with pytest.raises(type(failure)):
        ffmpeg.transcode(source, destination, ["-c", "copy"])
    assert not destination.exists()
    assert not list(tmp_path.glob("leviathan-*"))
    assert source.read_bytes() == b"original" and unrelated.read_text() == "keep"
    with pytest.raises(MediaError, match="overwritten"):
        ffmpeg.transcode(source, source, [])


def test_output_collision_at_finalize_never_deletes_other_file(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "result.mp4"
    source.write_bytes(b"original")

    def concurrent_writer(args, **kwargs):
        Path(args[-1]).write_bytes(b"render")
        destination.write_bytes(b"other writer")

    ffmpeg = FFmpeg(SimpleNamespace(resolve=lambda name: name), SimpleNamespace(run=concurrent_writer))
    with pytest.raises(MediaError):
        ffmpeg.transcode(source, destination, [])
    assert destination.read_bytes() == b"other writer"
