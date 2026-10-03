"""Coordinates temporary audio extraction, local transcription and persistence."""

from pathlib import Path
from tempfile import TemporaryDirectory
from leviathan_clipper.domain.cancellation import check_cancelled
from leviathan_clipper.domain.transcript import Transcript, TranscriptionError


class TranscriptionService:
    def __init__(self, ffmpeg, transcriber, store):
        self.ffmpeg, self.transcriber, self.store = ffmpeg, transcriber, store

    def generate(self, source, settings, cancel, progress):
        check_cancelled(cancel)
        if not source.has_audio:
            raise TranscriptionError("The selected video has no audio stream to transcribe.")
        try:
            before = source.path.stat()
            progress(0, "Extracting audio…")
            with TemporaryDirectory(prefix="leviathan-audio-") as work:
                audio = Path(work) / "speech.wav"
                self.ffmpeg.transcode(
                    source.path, audio, ["-map", "0:a:0", "-vn", "-af", "aresample=async=1:first_pts=0",
                                         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"],
                    cancel=cancel, progress=lambda seconds: progress(
                        0.2 * min(1, seconds / source.duration), "Extracting audio…",
                    ),
                )
                check_cancelled(cancel)
                language, segments = self.transcriber.transcribe(
                    audio, settings, source.duration, cancel,
                    lambda fraction, message: progress(0.2 + 0.75 * fraction, message),
                )
                check_cancelled(cancel)
            after = source.path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise TranscriptionError("The source changed during transcription. Re-import it and try again.")
            transcript = Transcript(source.path, source.duration, before.st_size, before.st_mtime_ns,
                                    language, settings.model, segments)
            progress(1, "Transcription complete." if segments else "No speech detected.")
            return transcript
        except (OSError, ValueError) as exc:
            raise TranscriptionError(f"Could not transcribe this source: {exc}") from exc

    def save(self, transcript, path, cancel, progress):
        progress(0, "Saving transcript…")
        result = self.store.save(transcript, path, cancel)
        progress(1, "Transcript saved.")
        return result

    def load(self, source, path, cancel, progress):
        progress(0, "Loading transcript…")
        transcript = self.store.load(path, cancel)
        try:
            stat = source.path.stat()
        except OSError as exc:
            raise TranscriptionError(f"The source is missing or unreadable: {exc}") from exc
        if (transcript.source_path.resolve() != source.path.resolve()
                or abs(transcript.source_duration - source.duration) > 0.25
                or transcript.source_size != stat.st_size or transcript.source_mtime_ns != stat.st_mtime_ns):
            raise TranscriptionError("This transcript belongs to a different or modified source. Re-import or transcribe it.")
        check_cancelled(cancel)
        progress(1, "Transcript loaded without transcription.")
        return transcript
