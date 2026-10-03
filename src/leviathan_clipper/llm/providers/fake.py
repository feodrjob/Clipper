"""Deterministic test provider; no model or endpoint is needed."""

from collections import deque
from leviathan_clipper.domain.cancellation import check_cancelled


class FakeProvider:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.requests = []

    def check_connection(self, cancel):
        check_cancelled(cancel)
        return "Connected to test provider."

    def generate(self, request, cancel):
        check_cancelled(cancel)
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("No configured fake response remains.")
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response(request) if callable(response) else response
