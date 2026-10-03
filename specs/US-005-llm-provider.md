# Goal
Add a replaceable LLM interface and an initial Ollama adapter.

# Requirements
- Define provider requests, responses, errors, and configurable endpoint/model settings.
- Implement Ollama HTTP calls with timeouts and structured-output requests.
- Provide a fake adapter for tests and validate returned JSON locally.

# Acceptance Criteria
- Services can substitute the fake provider without GUI changes.
- Local Qwen can return validated structured data when Ollama is available.
- Unreachable endpoints, invalid JSON, and unsupported schema behavior are handled explicitly.

# Dependencies
- US-001.

# Tests / Definition of Done
- Test HTTP request/response mapping, timeouts, configuration, and malformed responses using mocks.
- Document and run an opt-in Ollama smoke check when a local model is available.
