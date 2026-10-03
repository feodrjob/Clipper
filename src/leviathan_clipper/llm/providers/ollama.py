"""Ollama HTTP adapter. No SDK, model download, GUI or domain-analysis imports."""

from dataclasses import asdict
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from leviathan_clipper.domain.cancellation import check_cancelled
from leviathan_clipper.llm.contracts import ProviderError
from leviathan_clipper.llm.validation import strict_json


class OllamaProvider:
    def __init__(self, config, transport=None):
        self.config = config
        # Explicit endpoints are contacted directly; a system proxy must not intercept localhost.
        self.transport = transport or build_opener(ProxyHandler({})).open

    def _request(self, route, cancel, body=None, timeout=None):
        check_cancelled(cancel)
        payload = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8") if body is not None else None
        request = Request(self.config.endpoint.rstrip("/") + route, data=payload,
                          headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
        try:
            with self.transport(request, timeout=timeout or self.config.timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ProviderError("Provider response exceeds the 2 MiB limit.", "invalid_response")
            check_cancelled(cancel)
            data = strict_json(raw)
            if not isinstance(data, dict):
                raise ProviderError("Expected an object in the Ollama HTTP response.", "invalid_response")
            if data.get("error"):
                raise ProviderError(f"Ollama error: {str(data['error'])[:400]}", "http")
            return data
        except HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            if exc.code in {400, 422} and body and isinstance(body.get("format"), dict):
                raise ProviderError(
                    f"Ollama rejected the schema/request (HTTP {exc.code}). Check runtime/model support "
                    f"or select JSON mode; local validation still applies. {detail}", "schema_unsupported",
                ) from exc
            raise ProviderError(f"Ollama HTTP {exc.code}: {detail}", "http") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ProviderError("Provider request timed out. Check the runtime or increase the timeout.", "timeout") from exc
        except (URLError, OSError) as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise ProviderError("Provider request timed out.", "timeout") from exc
            raise ProviderError(f"Cannot reach the configured provider endpoint: {exc}", "connection") from exc

    def check_connection(self, cancel):
        data = self._request("/api/tags", cancel, timeout=min(10, self.config.timeout))
        try:
            names = {item["name"] for item in data["models"]}
        except (KeyError, TypeError) as exc:
            raise ProviderError("Invalid Ollama model-list response.", "invalid_response") from exc
        requested = self.config.model
        if requested not in names and (":" in requested or f"{requested}:latest" not in names):
            raise ProviderError(f"Model '{requested}' is not installed at this endpoint. Provision it separately.", "model_missing")
        return f"Connected; model '{requested}' is installed."

    def generate(self, request, cancel):
        data = self._request("/api/chat", cancel, {
            "model": self.config.model,
            "messages": [asdict(message) for message in request.messages],
            "stream": False,
            "format": request.schema if self.config.schema_mode == "schema" else "json",
            "options": {"temperature": request.temperature, "seed": 0,
                        "num_ctx": self.config.context_tokens,
                        "num_predict": min(request.max_output_tokens, self.config.max_output_tokens)},
        })
        try:
            content = data["message"]["content"]
            if data.get("done") is not True or not isinstance(content, str) or not content.strip():
                raise ValueError("Incomplete response or missing text.")
            if data.get("done_reason") == "length":
                raise ValueError("Output limit reached; reduce the request or raise the output budget.")
            return content
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError(f"Invalid Ollama chat response: {exc}", "invalid_response") from exc
