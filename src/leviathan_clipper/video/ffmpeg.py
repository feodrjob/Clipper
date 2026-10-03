"""Media execution and ownership of temporary outputs."""

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from leviathan_clipper.domain.cancellation import check_cancelled
from leviathan_clipper.video.tools import MediaError, ProcessRunner, ToolPaths


class FFmpeg:
    def __init__(self, tools=None, runner=None):
        self.tools = tools or ToolPaths()
        self.runner = runner or ProcessRunner()

    def transcode(self, source, destination, output_args, *, cancel=None, progress=None):
        source, destination = Path(source).resolve(), Path(destination).resolve()
        cancel = cancel if cancel is not None else Event()
        check_cancelled(cancel)
        if not source.is_file():
            raise MediaError(f"Source file does not exist: {source}")
        if source == destination or destination.exists():
            raise MediaError("Choose a new output path; existing files cannot be overwritten.")
        created = False
        try:
            with TemporaryDirectory(prefix="leviathan-", dir=destination.parent) as work:
                temporary = Path(work) / ("output" + destination.suffix)
                self.runner.run([
                    self.tools.resolve("ffmpeg"), "-hide_banner", "-v", "error", "-nostdin",
                    "-n", "-progress", "pipe:1", "-nostats", "-protocol_whitelist", "file,pipe",
                    "-i", str(source), *output_args, str(temporary),
                ], cancel=cancel, progress=progress, capture=False)
                check_cancelled(cancel)
                if not temporary.is_file() or temporary.stat().st_size == 0:
                    raise MediaError("FFmpeg produced no usable output.")
                with destination.open("xb") as target:
                    created = True
                    with temporary.open("rb") as media:
                        while chunk := media.read(1024 * 1024):
                            check_cancelled(cancel)
                            target.write(chunk)
                check_cancelled(cancel)
            return destination
        except BaseException as exc:
            if created:
                destination.unlink(missing_ok=True)
            if isinstance(exc, OSError):
                raise MediaError(f"Could not write output: {exc}") from exc
            raise
