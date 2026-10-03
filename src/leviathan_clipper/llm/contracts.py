"""Provider-neutral messages, configuration and provider contract."""

from dataclasses import dataclass
import math
from threading import Event
from typing import Protocol
from urllib.parse import urlsplit


class ProviderError(Exception):
    def __init__(self, message, code="provider"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    endpoint: str
    model: str
    timeout: float = 120
    context_tokens: int = 8192
    max_output_tokens: int = 1024
    schema_mode: str = "schema"

    def __post_init__(self):
        address = urlsplit(self.endpoint)
        if (not self.provider.strip() or not self.model.strip() or address.scheme not in {"http", "https"}
                or not address.hostname or address.username or address.password or address.query or address.fragment):
            raise ValueError("Choose a provider, HTTP(S) endpoint without credentials/query, and model name.")
        if (not math.isfinite(self.timeout) or not 1 <= self.timeout <= 600
                or not 2048 <= self.context_tokens <= 32768
                or not 64 <= self.max_output_tokens <= 4096
                or self.max_output_tokens >= self.context_tokens
                or self.schema_mode not in {"schema", "json"}):
            raise ValueError("Invalid timeout, context/output limits, or structured-output mode.")


@dataclass(frozen=True)
class Message:
    role: str
    content: str

    def __post_init__(self):
        if self.role not in {"system", "user", "assistant"} or not isinstance(self.content, str):
            raise ValueError("Invalid chat message.")


@dataclass(frozen=True)
class GenerationRequest:
    messages: tuple[Message, ...]
    schema: dict
    max_output_tokens: int = 1024
    temperature: float = 0


class LLMProvider(Protocol):
    def generate(self, request: GenerationRequest, cancel: Event) -> str: ...
    def check_connection(self, cancel: Event) -> str: ...
