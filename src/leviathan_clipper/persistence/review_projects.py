"""Self-contained, versioned review JSON with atomic saves."""

from dataclasses import asdict
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from leviathan_clipper.domain.cancellation import check_cancelled
from leviathan_clipper.domain.clips import Candidate
from leviathan_clipper.domain.media import SourceMedia
from leviathan_clipper.domain.review import ReviewError, ReviewProject
from leviathan_clipper.domain.transcript import Transcript, TranscriptSegment


class ReviewProjectStore:
    def save(self, project, path, cancel):
        path = Path(path).resolve()
        check_cancelled(cancel)
        if path == project.source.path.resolve() or (
                path.exists() and project.source.path.exists() and os.path.samefile(path, project.source.path)):
            raise ReviewError("A review project cannot overwrite the source video.")
        temporary = None
        try:
            data = asdict(project)
            data["schema_version"] = 1
            data["source"]["path"] = str(project.source.path)
            data["transcript"]["source_path"] = str(project.transcript.source_path)
            with NamedTemporaryFile("w", encoding="utf-8", prefix="leviathan-review-", suffix=".json",
                                    dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(data, handle, ensure_ascii=False, allow_nan=False, indent=2)
                handle.write("\n")
            check_cancelled(cancel)
            os.replace(temporary, path)
            return path
        except (OSError, ValueError, TypeError) as exc:
            raise ReviewError(f"Could not save review project: {exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def load(self, path, cancel):
        check_cancelled(cancel)
        try:
            path = Path(path)
            if path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("Project exceeds the 32 MiB limit.")
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.pop("schema_version") != 1:
                raise ValueError("Unsupported review project version.")
            source = data.pop("source")
            source["path"] = Path(source["path"])
            transcript = data.pop("transcript")
            transcript["source_path"] = Path(transcript["source_path"])
            transcript["segments"] = tuple(TranscriptSegment(**s) for s in transcript["segments"])
            candidates = []
            for item in data.pop("candidates"):
                item["quality"] = tuple(item["quality"])
                candidates.append(Candidate(**item))
            project = ReviewProject(SourceMedia(**source), Transcript(**transcript), tuple(candidates),
                                    tuple(data.pop("selected_ids")), tuple(data.pop("approved_ids")))
            if data:
                raise ValueError("Unexpected project fields.")
            check_cancelled(cancel)
            return project
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
            raise ReviewError(f"Could not load review project: {exc}") from exc
