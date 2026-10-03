"""Local-only faster-whisper adapter; imported lazily when processing starts."""

from pathlib import Path
from leviathan_clipper.domain.cancellation import CancelledError, check_cancelled
from leviathan_clipper.domain.transcript import TranscriptionError, TranscriptSegment


def resolve_local_model(model):
    path = Path(model)
    if not path.is_dir():
        if path.is_absolute():
            raise TranscriptionError(f"Local model folder does not exist: {path}")
        from faster_whisper.utils import download_model
        path = Path(download_model(model, local_files_only=True))
    missing = [name for name in ("model.bin", "config.json", "tokenizer.json") if not (path / name).is_file()]
    if missing:
        raise TranscriptionError(f"Incomplete local model folder {path}: missing {', '.join(missing)}.")
    return str(path.resolve())


class WhisperTranscriber:
    def __init__(self, model_factory=None):
        self.model_factory = model_factory

    def transcribe(self, audio, settings, duration, cancel, progress):
        check_cancelled(cancel)
        progress(0, "Loading local Whisper model…")
        try:
            factory = self.model_factory
            model_path = settings.model
            if factory is None:
                from faster_whisper import WhisperModel
                factory = WhisperModel
                # Missing tokenizers otherwise trigger an implicit upstream download.
                model_path = resolve_local_model(settings.model)
            model = factory(
                model_path, device=settings.device, compute_type=settings.compute_type,
                local_files_only=True,
            )
            check_cancelled(cancel)
            segments, info = model.transcribe(
                str(audio), language=settings.language, beam_size=5, vad_filter=False,
            )
            converted = []
            iterator = iter(segments)
            while True:
                check_cancelled(cancel)
                try:
                    segment = next(iterator)
                except StopIteration:
                    break
                check_cancelled(cancel)
                text = segment.text.strip()
                if not text:
                    continue
                if segment.end > duration + 0.25:
                    raise ValueError("A segment extends beyond the source duration.")
                converted.append(TranscriptSegment(float(segment.start), min(float(segment.end), duration), text))
                progress(min(1, converted[-1].end / duration), "Transcribing locally…")
            check_cancelled(cancel)
            return info.language, tuple(converted)
        except CancelledError:
            raise
        except Exception as exc:
            raise TranscriptionError(
                f"Local transcription failed: {exc}. Choose a downloaded CTranslate2 Whisper "
                "model folder (or a cached model name), check the language code, and try CPU/int8 "
                "if GPU/precision support is unavailable. Models are not downloaded during processing."
            ) from exc
