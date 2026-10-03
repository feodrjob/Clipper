from io import BytesIO
import json
from threading import Event
from urllib.error import HTTPError, URLError

import pytest
from leviathan_clipper.application.providers import PROBE_SCHEMA, ProviderService
from leviathan_clipper.domain.cancellation import CancelledError
from leviathan_clipper.llm.contracts import GenerationRequest, Message, ProviderConfig, ProviderError
from leviathan_clipper.llm.providers.fake import FakeProvider
from leviathan_clipper.llm.providers.ollama import OllamaProvider
from leviathan_clipper.llm.validation import validate_response


def config(**changes):
    values = dict(provider="ollama", endpoint="http://localhost:11434/proxy", model="some-model")
    values.update(changes)
    return ProviderConfig(**values)


def request():
    return GenerationRequest((Message("user", "JSON please"),), PROBE_SCHEMA, 64)


def test_ollama_mapping_and_json_mode():
    calls = []
    def transport(req, **kw):
        calls.append((req, kw))
        return BytesIO(json.dumps({"done": True, "message": {"content": '{"status":"ok"}'}}).encode())
    provider = OllamaProvider(config(), transport)
    assert provider.generate(request(), Event()) == '{"status":"ok"}'
    req, options = calls[0]
    data = json.loads(req.data)
    assert req.full_url == "http://localhost:11434/proxy/api/chat" and req.method == "POST"
    assert data["model"] == "some-model" and data["stream"] is False
    assert data["format"] == PROBE_SCHEMA and data["messages"] == [{"role": "user", "content": "JSON please"}]
    assert data["options"] == {"temperature": 0, "seed": 0, "num_ctx": 8192, "num_predict": 64}
    assert options == {"timeout": 120}
    OllamaProvider(config(schema_mode="json"), transport).generate(request(), Event())
    assert json.loads(calls[-1][0].data)["format"] == "json"


@pytest.mark.parametrize("data", [{}, {"done": False, "message": {"content": "x"}},
    {"done": True, "message": {"content": 7}}, {"done": True, "done_reason": "length", "message": {"content": "x"}},
    [], "invalid"])
def test_malformed_envelopes_are_typed_errors(data):
    raw = data.encode() if isinstance(data, str) else json.dumps(data).encode()
    provider = OllamaProvider(config(), lambda *a, **kw: BytesIO(raw))
    with pytest.raises(ProviderError) as failure:
        provider.generate(request(), Event())
    assert failure.value.code == "invalid_response"


@pytest.mark.parametrize("error,code", [(TimeoutError("slow"), "timeout"), (URLError("offline"), "connection"),
    (HTTPError("url", 422, "no schema", {}, BytesIO(b"unsupported format")), "schema_unsupported"),
    (HTTPError("url", 404, "missing", {}, BytesIO(b"not found")), "http")])
def test_transport_errors_are_actionable(error, code):
    def fail(*a, **kw):
        raise error
    with pytest.raises(ProviderError) as failure:
        OllamaProvider(config(), fail).generate(request(), Event())
    assert failure.value.code == code


def test_connection_checks_installed_model_and_cancel():
    calls = []
    def transport(req, **kw):
        calls.append(req.full_url)
        return BytesIO(b'{"models":[{"name":"some-model:latest"}]}')
    assert "installed" in OllamaProvider(config(), transport).check_connection(Event())
    assert calls == ["http://localhost:11434/proxy/api/tags"]
    with pytest.raises(ProviderError, match="not installed"):
        OllamaProvider(config(model="missing"), transport).check_connection(Event())
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        OllamaProvider(config(), transport).generate(request(), cancel)


@pytest.mark.parametrize("text", ['{"status":"wrong"}', '```json\n{"status":"ok"}\n```', '{"status":NaN}',
    '{"status":"ok","extra":1}', 'null', '{"status":"ok"} trailing'])
def test_strict_schema_validation(text):
    with pytest.raises(ProviderError) as failure:
        validate_response(text, PROBE_SCHEMA)
    assert failure.value.code == "invalid_response"


def test_fake_substitution_validates_and_checks_connection():
    fake = FakeProvider(['{"status":"ok"}', '{"status":"wrong"}'])
    service = ProviderService({"test": lambda config: fake})
    settings = config(provider="test")
    assert "verified" in service.test_connection(settings, Event(), lambda *a: None)
    with pytest.raises(ProviderError):
        service.generate_json(settings, request(), Event())
    assert len(fake.requests) == 2
    with pytest.raises(ProviderError, match="not registered"):
        service.create(config(provider="other"))


@pytest.mark.parametrize("changes", [dict(endpoint="file:///video"), dict(endpoint="http://user:pass@localhost"),
    dict(endpoint="http://localhost?x=1"), dict(model=""), dict(timeout=float("nan")),
    dict(max_output_tokens=4096, context_tokens=2048)])
def test_invalid_configuration(changes):
    with pytest.raises(ValueError):
        config(**changes)
