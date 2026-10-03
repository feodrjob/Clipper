"""Asynchronous source playback; no rendered clip or transcoding."""

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
import math


class IntervalPreview(QObject):
    status = Signal(str)
    failed = Signal(str)
    position = Signal(float)
    finished = Signal()

    def __init__(self, video_output, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(video_output)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.errorOccurred.connect(lambda error, message: self._error(message))
        self.player.positionChanged.connect(self._position)
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(lambda: self._position(self.player.position()))
        self._pending = False
        self._active = False
        self.start_ms, self.end_ms = 0, 0

    def play(self, source, start, end):
        self.stop()
        if not all(math.isfinite(value) for value in (start, end)) or not 0 <= start < end <= source.duration:
            self._error("interval is outside the source bounds")
            return
        self.start_ms, self.end_ms = round(start * 1000), round(end * 1000)
        self._pending = True
        url = QUrl.fromLocalFile(str(source.path))
        self.status.emit("Loading source preview…")
        if self.player.source() != url:
            self.player.setSource(url)
        elif self.player.mediaStatus() in {QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia,
                                           QMediaPlayer.MediaStatus.EndOfMedia}:
            self._start()

    def _start(self):
        if not self._pending:
            return
        self._pending = False
        self.player.setPosition(self.start_ms)
        self._active = True
        self.player.play()
        self.timer.start()
        self.status.emit("Playing source interval.")

    def _media_status(self, status):
        if status in {QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia}:
            self._start()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._error(self.player.errorString())
        elif status == QMediaPlayer.MediaStatus.EndOfMedia and self._active:
            self._complete()

    def _position(self, milliseconds):
        self.position.emit(milliseconds / 1000)
        if self._active and milliseconds >= self.end_ms:
            self._complete()

    def _complete(self):
        self._active = False
        self.timer.stop()
        self.player.pause()
        self.status.emit("Preview finished.")
        self.finished.emit()

    def _error(self, message):
        self.stop()
        self.failed.emit(f"Cannot preview this source: {message or 'unsupported media/codec'}.")

    def stop(self):
        self._pending = False
        self._active = False
        self.timer.stop()
        self.player.stop()
