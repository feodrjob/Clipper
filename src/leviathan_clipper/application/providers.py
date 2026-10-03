"""Provider composition and validation used by UI and analysis services."""

import os
from leviathan_clipper.domain.cancellation import check_cancelled
from leviathan_clipper.llm.contracts import GenerationRequest, Message, ProviderError
from leviathan_clipper.llm.providers.ollama import OllamaProvider
from leviathan_clipper.llm.validation import validate_response


PROBE_SCHEMA = {"type": "object", "properties": {"status": {"const": "ok"}},
                "required": ["status"], "additionalProperties": False}


class ProviderService:
    def __init__(self, factories=None):
        self.factories = dict(factories) if factories is not None else {"ollama": OllamaProvider}

    @property
    def provider_names(self):
        return tuple(self.factories)

    def defaults(self):
        return {"provider": os.environ.get("LEVIATHAN_LLM_PROVIDER", "ollama"),
                "endpoint": os.environ.get("LEVIATHAN_LLM_ENDPOINT", "http://127.0.0.1:11434"),
                "model": os.environ.get("LEVIATHAN_LLM_MODEL", "")}

    def create(self, config):
        if config.provider not in self.factories:
            raise ProviderError(f"Provider '{config.provider}' is not registered.", "configuration")
        return self.factories[config.provider](config)

    def generate_json(self, config, request, cancel):
        check_cancelled(cancel)
        response = self.create(config).generate(request, cancel)
        check_cancelled(cancel)
        return validate_response(response, request.schema)

    def test_connection(self, config, cancel, progress):
        progress(0, "Checking configured provider and model…")
        message = self.create(config).check_connection(cancel)
        self.generate_json(config, GenerationRequest((
            Message("system", 'Return only JSON: {"status":"ok"}.'),
            Message("user", "Confirm structured output."),
        ), PROBE_SCHEMA, max_output_tokens=64), cancel)
        progress(1, "Connection and structured output verified.")
        return message + " Structured output verified."
