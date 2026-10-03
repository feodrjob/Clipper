"""One background operation at a time; no processing queue."""

from threading import Event
from PySide6.QtCore import QThread, Signal
from leviathan_clipper.domain.cancellation import CancelledError, check_cancelled


class TaskWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(float, str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.cancel_event = Event()

    def run(self):
        try:
            result = self.operation(self.cancel_event, self.progress.emit)
            check_cancelled(self.cancel_event)
        except CancelledError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc) or type(exc).__name__)
        else:
            self.succeeded.emit(result)

    def cancel(self):
        self.cancel_event.set()
