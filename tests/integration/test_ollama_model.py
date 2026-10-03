import os
from threading import Event
import pytest
from leviathan_clipper.application.providers import ProviderService
from leviathan_clipper.llm.contracts import ProviderConfig


@pytest.mark.ollama_model
def test_configured_local_ollama_structured_output():
    model = os.environ.get("LEVIATHAN_LLM_MODEL")
    assert model, "Set LEVIATHAN_LLM_MODEL to an installed local model (for example Qwen)"
    settings = ProviderConfig("ollama", os.environ.get("LEVIATHAN_LLM_ENDPOINT", "http://127.0.0.1:11434"), model)
    assert "verified" in ProviderService().test_connection(settings, Event(), lambda *a: None)
