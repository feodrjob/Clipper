"""Executable discovery and cancellable argument-list subprocess execution."""

from collections import deque
from dataclasses import dataclass
import os
from pathlib import Path
from queue import Empty, Queue
import shutil
import subprocess
from threading import Event, Thread
import time
from leviathan_clipper.domain.cancellation import check_cancelled


class MediaError(Exception):
    """An actionable tool or media error."""


@dataclass(frozen=True)
class ToolPaths:
    ffmpeg: str | None = None
    ffprobe: str | None = None

    def resolve(self, name: str) -> str:
        if name not in {"ffmpeg", "ffprobe"}:
            raise ValueError("Unknown media tool.")
        configured = getattr(self, name) or os.environ.get(f"LEVIATHAN_{name.upper()}")
        found = shutil.which(configured or name)
        if not found:
            raise MediaError(
                f"{name} was not found. Install FFmpeg and add its bin directory to PATH, "
                f"or set LEVIATHAN_{name.upper()} to the executable path."
            )
        return str(Path(found).resolve())


class ProcessRunner:
    def run(self, args, *, cancel=None, progress=None, timeout=None, capture=True):
        cancel = cancel if cancel is not None else Event()
        check_cancelled(cancel)
        try:
            process = subprocess.Popen(
                [str(arg) for arg in args], shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except OSError as exc:
            raise MediaError(f"Could not start {args[0]}: {exc}") from exc
        lines = Queue()
        errors = deque(maxlen=100)

        def read_stdout():
            for line in process.stdout:
                lines.put(line)

        def read_stderr():
            for line in process.stderr:
                errors.append(line)

        readers = [Thread(target=read_stdout, daemon=True), Thread(target=read_stderr, daemon=True)]
        for reader in readers:
            reader.start()
        output = []
        started = time.monotonic()

        def consume(line):
            if capture:
                output.append(line)
            if progress and line.startswith("out_time_us="):
                try:
                    seconds = max(0, int(line.partition("=")[2])) / 1_000_000
                except ValueError:
                    return
                progress(seconds)

        try:
            while process.poll() is None:
                check_cancelled(cancel)
                if timeout is not None and time.monotonic() - started > timeout:
                    raise MediaError(f"{Path(args[0]).name} timed out after {timeout:g} seconds.")
                try:
                    consume(lines.get(timeout=0.05))
                except Empty:
                    pass
            for reader in readers:
                reader.join()
            while not lines.empty():
                consume(lines.get_nowait())
            check_cancelled(cancel)
            if process.returncode:
                detail = "".join(errors)[-4000:].strip()
                raise MediaError(f"{Path(args[0]).name} failed (exit {process.returncode}): {detail}")
            return "".join(output)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for reader in readers:
                reader.join(timeout=2)
            process.stdout.close()
            process.stderr.close()
