# Architecture

Use a single Python 3.12 application with PySide6 and small modules organized by responsibility. Start with plain dataclasses and explicit service calls. Do not introduce distributed services, a plugin framework, or a dependency injection framework.

## Boundaries

| Layer/module | Responsibility |
| --- | --- |
| UI | Windows, dialogs, review controls, and progress presentation; invokes application services only. |
| Application/services | Coordinates import, transcription, analysis, review, render, and export; owns job lifecycle and cancellation. |
| Domain | Provider-neutral models for source media, timestamped transcript segments, candidates, clip selections, ad presets/placements, render settings, and jobs. No Qt or tool execution. |
| Transcription | faster-whisper adapter; returns timestamped segments in source seconds and reports progress/errors. |
| LLM providers | Provider contract, response validation primitives, and adapters. Initial Ollama HTTP adapter with configurable Qwen model. |
| Clip analysis | Chunking, prompts, candidate validation, deduplication, and optional ranking using the provider contract. |
| Video processing | FFprobe metadata, FFmpeg argument construction/process execution, cuts, reframing, tracking, compositing, and fallback rendering. |
| Subtitles | Converts timestamped transcript segments into styled ASS using the edited timeline. |
| Advertisements | Library management, asset validation, preset selection, and placement planning; delegates media execution to video processing. |
| Configuration/persistence | Settings and project/library serialization, path resolution, and schema versions. |
| Export | Validates export plans, requests renders, verifies outputs, and finalizes MP4 files. |

Dependencies flow from UI to application services to domain and adapters. Adapters may use domain types but never import UI. Services receive concrete adapters at startup through simple constructor arguments. Domain code stays independent of external libraries.

## Processing flow and timeline

Import/FFprobe → local transcription → chunked LLM analysis → candidate review → render plan → video/subtitle/ad composition → verified MP4 export.

Keep all source timestamps in seconds relative to the original video. A render plan explicitly maps selected source intervals to output intervals, including inserted ads. Video ads shift subsequent output timestamps; banners use final output timestamps. Suppress source subtitles during video ads and shift later subtitles to remain synchronized. Apply overlays and subtitles on the final 9:16 composition.

Face tracking is a video processing concern. Begin with a configurable deterministic fallback; add OpenCV and/or MediaPipe tracking behind that boundary. Face detections alone do not reliably identify the active speaker. Low confidence, missing detections, and multiple faces must have defined fallback behavior.

## Replaceable LLM providers

Define a small provider interface that accepts messages, a requested JSON schema, and generation options, and returns response text or a typed provider error. Clip analysis owns prompt construction and domain validation. Provider configuration includes runtime, base URL, model identifier, timeout, and generation limits.

Implement Ollama first. Later adapters can support LM Studio, llama.cpp, vLLM, and OpenAI-compatible endpoints without changes to GUI or candidate models. Do not assume every runtime shares an API or supports schema enforcement; validate JSON locally for all providers, with bounded retries and useful errors. No model names are hard-coded into domain or UI behavior. Remote or paid endpoints require explicit user configuration and are not needed for normal processing.

## Execution and storage

Run expensive work outside the Qt GUI thread through a small background worker abstraction. Workers report progress and results to services/UI through signals; they never mutate widgets. Serialize heavy jobs initially to limit GPU/CPU contention. Support cancellation at safe checkpoints and terminate owned FFmpeg processes safely.

Use FFmpeg/FFprobe subprocess argument lists without shell interpolation. Centralize executable discovery and diagnostics. Keep large media on disk and stream/process intervals rather than loading entire videos into memory. Export to temporary files and finalize only verified successful outputs; preserve original sources and avoid silent overwrites.

Begin with versioned JSON for settings, projects, transcripts, and ad metadata. Store preferences/library metadata in the Windows user data directory; project files reference media paths and report missing assets. Separate temporary job files from persistent data. Credentials, if future providers need them, must not enter project files or logs.

## Proposed directory tree

US-001 creates the package boundaries below. US-002 and its US-003 dependency add `domain/media.py`, `domain/cancellation.py`, `application/import_video.py`, `application/tasks.py`, and `video/{tools,probe,ffmpeg}.py`. Import workers inspect metadata; only success callbacks on the GUI thread commit the current source. The process runner drains both output pipes, reports FFmpeg progress in seconds, and terminates/reaps owned processes on cancellation. Each transcode owns a private temporary directory and exclusively creates its final output; failures clean only owned files. Executable paths come from explicit configuration, environment, or PATH, resolved only when needed. Later responsibilities remain planned; empty packages contain no feature implementations. Tests generate small media fixtures on demand. Packaging remains deferred.

```text
LeviathanClipper/
├── AGENTS.md
├── docs/
│   ├── PRODUCT.md
│   ├── ARCHITECTURE.md
│   └── PROJECT_AUDIT.md
├── specs/
│   └── US-001-...md through US-015-...md
├── pyproject.toml
├── src/leviathan_clipper/
│   ├── __main__.py
│   ├── ui/
│   ├── application/
│   ├── domain/
│   ├── transcription/
│   ├── llm/                 # contract and provider adapters
│   │   └── providers/
│   ├── analysis/
│   ├── video/
│   ├── subtitles/
│   ├── advertisements/
│   ├── persistence/
│   └── export/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── packaging/               # later PyInstaller configuration
```

## Implemented transcription boundary (US-004)

`domain/transcript.py` defines settings, segments, and transcripts without Qt or inference imports. `application/transcribe_video.py` coordinates temporary first-stream audio extraction, `transcription/whisper.py`, and `persistence/transcripts.py`. Startup wires these adapters, and UI invokes only services through the single-operation worker. Local model/device/precision/language are configurable; faster-whisper is imported only during a requested transcription. Cached models resolve locally, and required tokenizer/config/weight files are checked before loading to prevent implicit downloads. No paid API or runtime network access is required.

Extraction produces mono 16 kHz PCM WAV with `aresample` alignment to source time zero, retaining delayed audio silence. Segments are ordered, finite, and within source duration; small decoder rounding at the end is clamped. Transcript JSON has schema version 1, source path/duration/size/mtime, language, model, and segment data. Atomic saves cannot overwrite the source; loading verifies source identity and never runs inference. Review-project persistence is described below; general settings persistence remains planned.

Cancellation is cooperative around model initialization and segment decoding; native inference already executing must reach a checkpoint. FFmpeg cancellation actively terminates/reaps its process. Temporary audio is scoped to the service call. The current faster-whisper decoder buffers audio, so long recordings need adequate memory and disk; video frames remain on disk. CPU/int8 is verified; CUDA support is configurable but has not been validated on this host. PyAV is capped below 19 for compatibility with faster-whisper 1.2's audio decoder.

## Validation strategy

US-005 implements `llm/contracts.py`, strict JSON/schema validation, `llm/providers/ollama.py`, and a deterministic fake provider. `application/providers.py` composes adapters by registered provider name, independent of model identity. UI configures provider/endpoint/model and delegates the connection/structured-output test to the existing worker. Startup does no HTTP work. Other runtime APIs require adapters, not GUI or domain changes. JSON mode is an explicit fallback for runtimes that reject schemas; local validation remains mandatory. HTTP requests have configurable socket timeouts and response-size limits; cancellation is checked before and after in-flight requests.

US-006 adds `domain/clips.py`, `analysis/chunks.py`, `analysis/analyzer.py`, `application/analyze_clips.py`, and `ui/analysis_panel.py`. Input chunks have byte and row limits, bounded overlap, and original source-index references. Discovery output uses a schema plus semantic duration/content checks; source text/timestamps are reconstructed locally. Aggregation removes substantial overlaps; optional ranking operates on bounded summary batches; deterministic final selection avoids overlaps and explains shortfalls. JSON/schema errors allow one bounded repair request, then skip/fallback; transport/configuration errors abort. Byte counts are a conservative tokenizer-independent estimate, not exact token counts for every possible runtime. Suggestions remain distinct from user-approved selections.

US-007 adds `domain/review.py`, `application/review_clips.py`, `persistence/review_projects.py`, `ui/review_panel.py`, and `video/preview.py`. Immutable review snapshots separate selected IDs from explicit approved IDs. The service validates edited source intervals, updates transcript excerpts, and revokes approval after any edit/selection change. `approved_selection()` is the future rendering handoff and rejects unapproved selections; no rendering implementation exists yet. Versioned atomic review JSON includes source/transcript/candidates/selection/approval and verifies source identity and probed metadata on reload, without inference.

The video layer's `IntervalPreview` owns asynchronous QMediaPlayer playback with a video output supplied by the UI. It seeks to source start and pauses at end, exposes status/errors, and creates no rendered files or FFmpeg subprocesses. Qt manages media decoding outside synchronous widget callbacks. Preview timing is approximate, not a rendering boundary guarantee; codec support comes from the installed Qt Multimedia backend. Persistence/probing still use the background application worker, and starting a job stops playback. Domain/review services remain independent of Qt.

Use pytest for deterministic domain/service tests with fake providers and workers. Use small synthetic media for FFmpeg integration tests and timing/output checks. Keep real-model smoke tests opt-in, since they require model files and hardware. GUI checks verify service wiring and responsiveness. Later Windows build checks run on a clean machine with documented external tool/model requirements.
