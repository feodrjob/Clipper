"""Versioned JSON transcript files, written atomically."""

from dataclasses import asdict
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Event

from leviathan_clipper.domain.cancellation import check_cancelled
from leviathan_clipper.domain.transcript import Transcript, TranscriptSegment, TranscriptionError


class TranscriptStore:
    def save(self, transcript, path, cancel=None):
        path = Path(path).resolve()
        cancel = cancel if cancel is not None else Event()
        check_cancelled(cancel)
        if path == transcript.source_path.resolve() or (
                path.exists() and transcript.source_path.exists() and
                os.path.samefile(path, transcript.source_path)):
            raise TranscriptionError("A transcript cannot overwrite the source media file.")
        temporary = None
        try:
            data = asdict(transcript)
            data["source_path"] = str(transcript.source_path)
            data["schema_version"] = 1
            with NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", prefix="leviathan-",
                                    dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(data, handle, ensure_ascii=False, allow_nan=False, indent=2)
                handle.write("\n")
            check_cancelled(cancel)
            os.replace(temporary, path)
            return path
        except (OSError, TypeError, ValueError) as exc:
            raise TranscriptionError(f"Could not save transcript: {exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def load(self, path, cancel=None):
        cancel = cancel if cancel is not None else Event()
        check_cancelled(cancel)
        try:
            path = Path(path)
            if path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("Transcript file exceeds the 32 MiB limit.")
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.pop("schema_version") != 1:
                raise ValueError("Unsupported transcript schema version.")
            data["source_path"] = Path(data["source_path"])
            data["segments"] = tuple(TranscriptSegment(**s) for s in data["segments"])
            transcript = Transcript(**data)
            check_cancelled(cancel)
            return transcript
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise TranscriptionError(f"Could not load transcript: {exc}") from exc
