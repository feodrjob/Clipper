"""Opt-in, offline, CPU smoke test with a provisioned model and speech WAV."""

import os
from pathlib import Path
import socket
import subprocess
from threading import Event

import pytest
from leviathan_clipper.application.transcribe_video import TranscriptionService
from leviathan_clipper.domain.transcript import TranscriptionSettings
from leviathan_clipper.persistence.transcripts import TranscriptStore
from leviathan_clipper.transcription.whisper import WhisperTranscriber
from leviathan_clipper.video.ffmpeg import FFmpeg
from leviathan_clipper.video.probe import VideoProbe


@pytest.mark.local_model
def test_local_cpu_speech_transcription_and_reload(tools, tmp_path, monkeypatch):
    model = os.environ.get("LEVIATHAN_TEST_MODEL")
    speech = os.environ.get("LEVIATHAN_TEST_SPEECH")
    assert model and Path(model).is_dir(), "Set LEVIATHAN_TEST_MODEL to a downloaded model folder"
    assert speech and Path(speech).is_file(), "Set LEVIATHAN_TEST_SPEECH to a short speech WAV"
    source = tmp_path / "speech source.mp4"
    subprocess.run([
        tools.resolve("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=blue:s=160x90:r=25",
        "-i", speech, "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(source),
    ], check=True, capture_output=True, timeout=20)

    def forbid_network(*a, **kw):
        raise AssertionError("Local transcription attempted network access")
    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    media = VideoProbe(tools).probe(source)
    service = TranscriptionService(FFmpeg(tools), WhisperTranscriber(), TranscriptStore())
    transcript = service.generate(media, TranscriptionSettings(model, "cpu", "en", "int8"), Event(), lambda *a: None)
    assert transcript.segments, "Expected speech segments"
    assert all(0 <= s.start < s.end <= media.duration and s.text.strip() for s in transcript.segments)
    assert "local" in " ".join(s.text.lower() for s in transcript.segments)
    saved = tmp_path / "transcript.json"
    service.save(transcript, saved, Event(), lambda *a: None)
    monkeypatch.setattr(service.transcriber, "transcribe", lambda *a: pytest.fail("Reload should not transcribe"))
    assert service.load(media, saved, Event(), lambda *a: None) == transcript
