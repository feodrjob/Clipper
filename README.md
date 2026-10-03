# LeviathanClipper

A local Windows desktop application for producing vertical short clips from long videos. The current application supports video import, local transcription, configurable LLM providers, chunked moment analysis, and source-interval review with saved approvals. Rendering and later features are defined in `specs/`.

## Development setup (Windows PowerShell)

Use Python 3.12. From the repository root:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -e ".[dev]"
```

The explicit environment path avoids PowerShell activation requirements and preserves any existing `.venv` using another Python version. Set PyCharm's interpreter to `.venv312\Scripts\python.exe` when developing this project. Runtime dependencies are PySide6, faster-whisper, jsonschema, and their required dependencies; pytest is the development test dependency. PyAV is constrained to `<19` because faster-whisper 1.2 uses an API removed in [PyAV 19](https://github.com/PyAV-Org/PyAV/blob/main/CHANGELOG.rst). Setuptools is the build backend. No external Qt installation is needed.

## Launch

```powershell
.\.venv312\Scripts\python.exe -m leviathan_clipper
```

Alternatively use the installed Windows GUI launcher:

```powershell
.\.venv312\Scripts\leviathan-clipper.exe
```

Close the window with its standard close button. Startup creates only the application and window; it performs no media or AI processing. The root `main.py` is the original PyCharm sample, not the application launcher.

## Media tools and video import

Install a portable Windows FFmpeg build from a provider linked on the [FFmpeg download page](https://ffmpeg.org/download.html). Both `ffmpeg.exe` and `ffprobe.exe` are needed. Add its `bin` directory to PATH or configure the executable paths before launching:

```powershell
$env:LEVIATHAN_FFMPEG = "C:\Tools\ffmpeg\bin\ffmpeg.exe"
$env:LEVIATHAN_FFPROBE = "C:\Tools\ffmpeg\bin\ffprobe.exe"
```

For the portable build provisioned in this checkout:

```powershell
$env:LEVIATHAN_FFMPEG = (Resolve-Path ".tools\ffmpeg\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe").Path
$env:LEVIATHAN_FFPROBE = (Resolve-Path ".tools\ffmpeg\ffmpeg-9.0.2-essentials_build\bin\ffprobe.exe").Path
.\.venv312\Scripts\python.exe -m leviathan_clipper
```

Use **Import video…** to choose a local file. Metadata loads in the background; a failed or cancelled import retains the current source. The window displays duration in source seconds, coded dimensions, average frame rate (or unknown), and audio availability. Import never modifies the input. Cancel stops the current operation; closing during work requests cancellation and waits for cleanup. There is no processing queue.

Executable discovery is lazy, so missing tools do not prevent startup. Explicit service configuration takes precedence over environment settings, then PATH. Tests also discover the ignored checkout-local `.tools/ffmpeg/*/bin` build; the application uses the configuration above. Media integration checks generate small fixtures and skip explicitly if tools are unavailable. Process arguments and progress parsing follow the [FFmpeg](https://ffmpeg.org/ffmpeg.html) and [FFprobe](https://ffmpeg.org/ffprobe.html) documentation.

## Local transcription

Provision a converted faster-whisper/CTranslate2 model separately from normal processing. For example, download the [SYSTRAN tiny model](https://huggingface.co/Systran/faster-whisper-tiny) during setup:

```powershell
.\.venv312\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-tiny', local_dir='.models/faster-whisper-tiny', allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*','preprocessor_config.json'])"
$env:LEVIATHAN_WHISPER_MODEL = (Resolve-Path ".models\faster-whisper-tiny").Path
```

The tiny model is already provisioned in this checkout for validation. A local model folder must include `model.bin`, `config.json`, and `tokenizer.json`. Cached model names also work if the complete model is already available. The adapter resolves cached models with `local_files_only=True` and checks the tokenizer before initialization to prevent upstream fallback downloads. Missing files produce an error rather than a download. See the [faster-whisper project](https://github.com/SYSTRAN/faster-whisper) for model/device details.

Import a video with audio, choose a model, device and precision, optionally enter a language code (blank means auto-detect), then select **Transcribe locally**. CPU/int8 is the tested baseline; CUDA requires compatible GPU libraries and is optional. Transcription is never automatic on import or startup.

FFmpeg extracts the first audio stream as temporary mono 16 kHz PCM WAV, retaining leading silence for delayed audio. Transcript timestamps use source seconds. **Save transcript…** writes versioned JSON; **Load transcript…** reuses it without model execution after checking the selected source's path, duration, size, and modification time. Re-importing resets the displayed transcript; failed/cancelled operations preserve the previous successful result. A silent source is supported for import, but cannot be transcribed; no detected speech produces an empty transcript with a clear status.

Transcription cancellation is cooperative at model/segment boundaries. A native inference call already in progress must return before cleanup; closing the window waits safely. FFmpeg cancellation terminates its owned process. Temporary audio is removed after success, failure, or cancellation. Long recordings require temporary disk space and sufficient RAM for faster-whisper's audio decoding; whole-video frames are not loaded into memory.

## Validation

```powershell
.\.venv312\Scripts\python.exe -m pip check
.\.venv312\Scripts\python.exe -m pytest --collect-only -q
.\.venv312\Scripts\python.exe -m pytest -q
```

Tests cover domain/services, fake tool/model failures, real FFmpeg media fixtures, GUI responsiveness, transcript persistence, installed package imports, and window/event-loop shutdown. Qt uses offscreen mode by default. Startup smoke tests run in isolated subprocesses and reject unexpected external processes or network connections. The real-model test is opt-in and requires local assets; no test downloads them.

To include the real offline CPU transcription smoke test, provide a local model folder and a short speech WAV. This checkout contains an offline Windows-SAPI speech fixture used for validation:

```powershell
$env:LEVIATHAN_TEST_MODEL = (Resolve-Path ".models\faster-whisper-tiny").Path
$env:LEVIATHAN_TEST_SPEECH = (Resolve-Path ".tools\validation\speech.wav").Path
.\.venv312\Scripts\python.exe -m pytest --run-local-model -q
```

That test blocks socket connections during transcription, verifies source timestamp bounds and speech text, and reloads saved JSON with the transcriber disabled. Without `--run-local-model`, it is explicitly skipped.

To run the same startup checks with native Windows windows on an interactive desktop:

```powershell
$previousQtPlatform = $env:QT_QPA_PLATFORM
$env:QT_QPA_PLATFORM = "windows"
try {
    .\.venv312\Scripts\python.exe -m pytest tests/integration/test_startup.py tests/integration/test_import_ui.py tests/integration/test_transcription_ui.py -q
} finally {
    if ($null -eq $previousQtPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM
    } else {
        $env:QT_QPA_PLATFORM = $previousQtPlatform
    }
}
```

The native smoke checks close their windows automatically and restore any previous platform override.

## LLM provider configuration (US-005)

The **LLM provider** tab configures the registered provider, HTTP(S) base endpoint, model name, timeout, context/output token limits, and structured-output mode. Model names have no effect on application architecture. Ollama is the first adapter; other runtime adapters can be registered through the same contract. The deterministic fake provider is for tests and is not enabled in the normal application.

Defaults can be supplied with `LEVIATHAN_LLM_PROVIDER`, `LEVIATHAN_LLM_ENDPOINT`, and `LEVIATHAN_LLM_MODEL`. The model field is initially blank unless configured. Provision the runtime and model separately; the app never installs models or calls a paid API automatically. For example, use a locally installed Qwen model by entering its actual Ollama tag.

**Test connection and structured output** checks that the selected model is installed and generates/validates a small JSON response in the background. Ollama requests use the [chat API](https://docs.ollama.com/api/chat) and [structured output format](https://docs.ollama.com/capabilities/structured-outputs). If a runtime rejects JSON schemas, choose JSON mode explicitly; responses still undergo strict local schema validation. There is no silent downgrade or unbounded retry. In-flight HTTP cancellation reaches a checkpoint after the request returns or its configured socket timeout expires.

An opt-in runtime/model smoke test is available after starting local Ollama and provisioning a model:

```powershell
$env:LEVIATHAN_LLM_ENDPOINT = "http://127.0.0.1:11434"
$env:LEVIATHAN_LLM_MODEL = "YOUR_INSTALLED_MODEL_TAG"
.\.venv312\Scripts\python.exe -m pytest tests/integration/test_ollama_model.py --run-ollama -q
```

This test downloads nothing and must fail if the configured model/runtime is missing. Normal tests mock transport and substitute providers without Ollama. Schema validation uses [jsonschema](https://python-jsonschema.readthedocs.io/en/stable/validate/).

## Transcript clip analysis (US-006)

With a loaded/generated transcript and configured provider, open **Clip analysis**. Set desired count, duration bounds, chunk byte budget/overlap, and minimum score, then analyze. The pipeline is transcript → overlapping chunks → candidates → aggregation/deduplication → final suggestions. Optional second-pass ranking scores bounded candidate summaries; it never resends the full transcript. Suggestions are advisory until review.

Prompts contain timestamped transcript rows and source IDs only, never raw video, paths, or frames. Model responses reference source IDs; the app maps them to original timestamps and transcript text. Each request is checked against a conservative UTF-8 byte/context estimate with reserved schema/output space. Oversized segments are split as text while preserving their original time bounds. Small output/context budgets that cannot fit the schema receive a configuration error rather than an oversized request.

Candidates include title, score, reason, source text, and quality ratings for hook, context, humor, emotion, conflict, information, surprise, completeness, and ending. Final selection favors a strong interest signal and complete context/endings, removes substantial duplicates, and avoids overlapping suggestions. It returns fewer clips with an explanation when suitable moments are unavailable.

Invalid JSON/schema responses receive at most one deterministic re-prompt without echoing untrusted model text. A chunk still invalid is skipped with a warning; a failed ranking retains discovery scores. Connection/HTTP/schema-support errors abort with actionable feedback instead of repeated requests. Scores and local model quality are not guarantees of engaging content.

## Clip review (US-007)

Analysis opens **Clip review** with suggested candidates checked but unapproved. The table shows start/end source seconds, duration, title, and score. Select a row to inspect the reason, quality ratings, and transcript excerpt. Check/uncheck **Use** to change the selection. Enter start/end seconds and choose **Apply boundaries**; intervals must satisfy `0 ≤ start < end ≤ source duration`. Duration and transcript context update after a valid edit. Scores/reasons remain the original model's advisory assessment; inspect context again after an edit.

**Preview clip** plays the committed source interval with audio; **Stop preview** stops it. Playback is asynchronous through Qt Multimedia and creates no clip files. The player seeks to the start and pauses at the end; seek/stop precision depends on the decoder and event-loop timing, so preview is not a frame-accurate render. Unsupported/missing sources report errors. Editing boundaries or starting a background operation stops preview.

**Use selected clips** explicitly approves the current selection. Any later selection or boundary change revokes approval. The application service exposes only approved clips for a future rendering handoff; this milestone starts no renderer.

**Save review project…** stores versioned JSON containing source metadata, transcript, edited candidates, selections, and approvals. **Load review project…** restores these without Whisper or LLM execution; it verifies source path, size, modification time, and probed media metadata. The source must remain available and unchanged. Drafts may also be saved, but remain unapproved after reload. Loading/saving run in the background, and atomic saves cannot overwrite the original video. A successful new import/transcript resets the review; a failed load retains the current review.

To verify the requested GUI workflow on native Windows:

```powershell
$previousQtPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = "windows"
    .\.venv312\Scripts\python.exe -m pytest tests/integration/test_provider_ui.py tests/integration/test_analysis_ui.py tests/integration/test_review_ui.py tests/integration/test_startup.py -q
} finally {
    $env:QT_QPA_PLATFORM = $previousQtPlatform
}
```

## Development rules

Read `AGENTS.md`, `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, and the explicitly requested User Story before coding. The `src/` package separates UI, startup/application coordination, domain, and future adapters. Empty packages establish boundaries without implementing later stories.

Metadata uses [setuptools in pyproject.toml](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html); tests use [pytest's pyproject configuration](https://docs.pytest.org/en/stable/reference/customize.html). See [Qt for Python's setup guide](https://doc.qt.io/qtforpython-6/quickstart.html) for PySide6 installation details.
