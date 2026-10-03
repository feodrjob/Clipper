"""Cooperative cancellation shared by processing adapters."""

from threading import Event


class CancelledError(Exception):
    """The operation was explicitly cancelled."""


def check_cancelled(cancel: Event) -> None:
    if cancel.is_set():
        raise CancelledError("Operation cancelled.")
