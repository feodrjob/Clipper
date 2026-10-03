import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from leviathan_clipper.application.transcribe_video import TranscriptionService
from leviathan_clipper.domain.cancellation import CancelledError
from leviathan_clipper.domain.media import SourceMedia
from leviathan_clipper.domain.transcript import (
    Transcript, TranscriptSegment, TranscriptionError, TranscriptionSettings,
)
from leviathan_clipper.persistence.transcripts import TranscriptStore
from leviathan_clipper.transcription.whisper import WhisperTranscriber, resolve_local_model


def test_local_model_requires_tokenizer_before_loading(tmp_path):
    with pytest.raises(TranscriptionError, match="does not exist"):
        resolve_local_model(str(tmp_path / "missing"))
    for name in ("model.bin", "config.json"):
        (tmp_path / name).write_text("test")
    with pytest.raises(TranscriptionError, match="tokenizer.json"):
        resolve_local_model(str(tmp_path))
    (tmp_path / "tokenizer.json").write_text("test")
    assert resolve_local_model(str(tmp_path)) == str(tmp_path.resolve())


def test_cached_model_resolution_is_local_only(tmp_path, monkeypatch):
    import faster_whisper.utils
    calls = []
    for name in ("model.bin", "config.json", "tokenizer.json"):
        (tmp_path / name).write_text("test")
    def cached(name, **options):
        calls.append((name, options))
        return str(tmp_path)
    monkeypatch.setattr(faster_whisper.utils, "download_model", cached)
    assert resolve_local_model("tiny") == str(tmp_path.resolve())
    assert calls == [("tiny", {"local_files_only": True})]


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.mp4"
    path.write_bytes(b"original source")
    return SourceMedia(path, 10, 160, 90, 25, True)


def transcript_for(source):
    stat = source.path.stat()
    return Transcript(source.path, source.duration, stat.st_size, stat.st_mtime_ns, "en", "tiny",
                      (TranscriptSegment(0.5, 2.5, "Hello, мир!"),))


def fake_media():
    def extract(source, destination, output_args, **kwargs):
        assert "16000" in output_args and "pcm_s16le" in output_args
        Path(destination).write_bytes(b"audio")
        kwargs["progress"](1)
        return destination
    return SimpleNamespace(transcode=extract)


def test_adapter_local_only_settings_lazy_segments_and_progress(tmp_path):
    calls = []
    progress = []

    def factory(model, **kwargs):
        calls.append((model, kwargs))

        def transcribe(audio, **options):
            assert options == {"language": "ru", "beam_size": 5, "vad_filter": False}
            return iter([SimpleNamespace(start=0.5, end=2, text=" Привет! ")]), SimpleNamespace(language="ru")
        return SimpleNamespace(transcribe=transcribe)

    result = WhisperTranscriber(factory).transcribe(
        tmp_path / "audio.wav", TranscriptionSettings("folder", "cpu", "ru", "float32"),
        5, Event(), lambda *a: progress.append(a),
    )
    assert result == ("ru", (TranscriptSegment(0.5, 2, "Привет!"),))
    assert calls == [("folder", {"device": "cpu", "compute_type": "float32", "local_files_only": True})]
    assert progress[-1][0] == 0.4


@pytest.mark.parametrize("start,end,text", [(-1, 2, "text"), (2, 1, "text"), (0, float("nan"), "text"),
    (0, float("inf"), "text"), (0, 20, "text")])
def test_adapter_rejects_invalid_timestamps(start, end, text):
    factory = lambda *a, **kw: SimpleNamespace(transcribe=lambda *a, **kw: (
        iter([SimpleNamespace(start=start, end=end, text=text)]), SimpleNamespace(language="en"),
    ))
    with pytest.raises(TranscriptionError):
        WhisperTranscriber(factory).transcribe("a", TranscriptionSettings(), 5, Event(), lambda *a: None)


@pytest.mark.parametrize("error", [FileNotFoundError("missing model"), RuntimeError("CUDA unavailable")])
def test_adapter_model_hardware_errors_are_actionable(error):
    def fail(*a, **kw):
        raise error
    with pytest.raises(TranscriptionError, match="CPU/int8"):
        WhisperTranscriber(fail).transcribe("a", TranscriptionSettings(), 5, Event(), lambda *a: None)


def test_adapter_cancel_between_segments():
    cancel = Event()
    def segments():
        yield SimpleNamespace(start=0, end=1, text="first")
        cancel.set()
        yield SimpleNamespace(start=1, end=2, text="second")
    factory = lambda *a, **kw: SimpleNamespace(transcribe=lambda *a, **kw: (segments(), SimpleNamespace(language="en")))
    with pytest.raises(CancelledError):
        WhisperTranscriber(factory).transcribe("a", TranscriptionSettings(), 5, cancel, lambda *a: None)


def test_service_transcript_roundtrip_and_no_transcriber_on_load(source, tmp_path):
    audio_paths = []
    def transcribe(audio, settings, duration, cancel, progress):
        audio_paths.append(audio)
        assert audio.is_file()
        return "en", (TranscriptSegment(0.5, 2.5, "Hello, мир!"),)
    service = TranscriptionService(fake_media(), SimpleNamespace(transcribe=transcribe), TranscriptStore())
    transcript = service.generate(source, TranscriptionSettings(), Event(), lambda *a: None)
    assert transcript == transcript_for(source)
    assert all(not path.exists() for path in audio_paths)
    destination = tmp_path / "transcript.json"
    service.save(transcript, destination, Event(), lambda *a: None)
    service.transcriber.transcribe = lambda *a: pytest.fail("Loading must not transcribe")
    assert service.load(source, destination, Event(), lambda *a: None) == transcript
    assert "мир" in destination.read_text(encoding="utf-8")
    source.path.write_bytes(b"modified source")
    with pytest.raises(TranscriptionError, match="modified source"):
        service.load(source, destination, Event(), lambda *a: None)


@pytest.mark.parametrize("failure", [CancelledError("cancelled"), TranscriptionError("decode failed")])
def test_service_failure_removes_audio(source, failure):
    audio_paths = []
    def fail(audio, *args):
        audio_paths.append(audio)
        raise failure
    service = TranscriptionService(fake_media(), SimpleNamespace(transcribe=fail), TranscriptStore())
    with pytest.raises(type(failure)):
        service.generate(source, TranscriptionSettings(), Event(), lambda *a: None)
    assert audio_paths and all(not path.parent.exists() for path in audio_paths)
    assert source.path.read_bytes() == b"original source"


def test_service_rejects_no_audio_and_pre_cancel(source):
    service = TranscriptionService(None, None, None)
    silent = SourceMedia(source.path, 10, 160, 90, 25, False)
    with pytest.raises(TranscriptionError, match="no audio"):
        service.generate(silent, TranscriptionSettings(), Event(), lambda *a: None)
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        service.generate(source, TranscriptionSettings(), cancel, lambda *a: None)


def test_store_invalid_version_bounds_missing_file_and_source_protection(source, tmp_path):
    store = TranscriptStore()
    transcript = transcript_for(source)
    path = tmp_path / "saved.json"
    store.save(transcript, path)
    valid = json.loads(path.read_text(encoding="utf-8"))
    for data in [dict(valid, schema_version=99), dict(valid, segments=[{"start": 0, "end": 100, "text": "bad"}]),
                 dict(valid, segments=[{"start": -1, "end": 1, "text": "bad"}]), {}]:
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(TranscriptionError, match="load"):
            store.load(path)
    with pytest.raises(TranscriptionError):
        store.load(tmp_path / "missing.json")
    with pytest.raises(TranscriptionError, match="overwrite"):
        store.save(transcript, source.path)
    assert source.path.read_bytes() == b"original source"


def test_cancelled_save_preserves_existing_and_removes_temporary(source, tmp_path, monkeypatch):
    store = TranscriptStore()
    target = tmp_path / "existing.json"
    target.write_text("previous")
    cancel = Event()
    real_dump = json.dump
    def cancel_after_write(*a, **kw):
        real_dump(*a, **kw)
        cancel.set()
    monkeypatch.setattr(json, "dump", cancel_after_write)
    with pytest.raises(CancelledError):
        store.save(transcript_for(source), target, cancel)
    assert target.read_text() == "previous" and not list(tmp_path.glob("leviathan-*"))
