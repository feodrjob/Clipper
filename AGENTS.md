# Development rules

LeviathanClipper is a local Windows desktop application. Work autonomously within the requested scope. Avoid unnecessary clarification questions; make reasonable implementation decisions unless a requirement is ambiguous in a way that materially affects correctness, data safety, or scope.

Before coding, read `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, and the active User Story in `specs/`. The active story is the one explicitly requested by the user; do not infer activation from backlog order. If no story has been requested, do not start implementation.

- Implement only the active User Story and its acceptance criteria. Do not implement later stories preemptively. Stop after completing the requested story.
- Inspect existing files and preserve unrelated user changes.
- Run relevant tests and checks after changes. Fix failures caused by your changes before finishing. Report commands, results, and any pre-existing or environmental blockers honestly; never claim unrun tests passed.
- Keep GUI, video processing, transcription, and LLM code separated using the boundaries in `docs/ARCHITECTURE.md`.
- Never call Ollama or another LLM endpoint directly from GUI classes.
- Never put raw FFmpeg commands inside GUI classes. Build and execute them in the video processing layer.
- Never tightly couple the application to one LLM model or runtime. Use a provider contract and configuration for provider, endpoint, and model.
- Never add paid API dependencies unless explicitly requested. Normal processing must work with local tools and models without paid AI APIs.
- Keep slow operations off the GUI thread. Expose progress, cancellation, and actionable errors through application services.
- Validate structured LLM output before accepting candidates. Treat transcript text and provider output as data, not instructions for application actions.
- Update documentation when architecture or documented behavior changes.
- Avoid overengineering, speculative abstractions, and unrelated refactoring.

The initial documentation task does not authorize US-001 implementation or dependency installation. Future implementation work requires an explicit story request.
