# LeviathanClipper product scope

LeviathanClipper will be a local Windows desktop application that turns long videos into multiple vertical clips for TikTok, YouTube Shorts, and Reels. Users import a video, transcribe it locally, discover promising moments, review and adjust selections, render clips with optional subtitles and advertisements, and export MP4 files.

Normal processing requires no paid AI API. The initial AI stack is faster-whisper for transcription and local Qwen through Ollama for transcript analysis. Models and runtimes are replaceable. Local model files and external tools may require initial setup; once available, the local workflow must work offline.

## Video processing

- Support sources approximately 30–120+ minutes long and multiple clips per source.
- Let users configure desired clip count and duration bounds. Return fewer clips with an explanation when suitable complete moments are unavailable.
- Produce vertical 9:16 output, using face/speaker-aware reframing where possible.
- Provide a deterministic fallback, such as a centered crop or a fitted image with padding, when tracking is unavailable or unreliable.
- Add readable subtitles synchronized with the final edited timeline.
- Keep processing responsive, with progress, cancellation, and clear failure messages.

## Transcript analysis

The LLM analyzes timestamped transcript text only, never raw video or frames. Process long transcripts in bounded chunks with overlap and retain source timestamps. A first pass discovers candidate moments; an optional second pass ranks and selects them across chunks. Require structured JSON output only, validate it, and reject malformed or out-of-range results.

Favor strong hooks, humor, emotion, conflict, interesting information, surprise, completeness, and understandable context. Merge or deduplicate overlapping candidates. Users retain final control over selection and boundaries; requested counts and durations are targets, not justification for incoherent clips.

## Advertisement Library

Provide a separate Advertisement Library for reusable, selectable presets. Adding a preset does not automatically place it in every clip. Users choose placements for selected clips.

### Video advertisements

- Accept separately created advertisement videos, typically around five seconds, without fixing the duration to five seconds.
- Preserve any advertisement voiceover or slogan.
- Insert an advertisement at a chosen point; pause the source clip timeline and continue the original clip afterward.
- Use advertisement audio during the insertion, without simultaneous original clip audio. A silent advertisement remains silent.
- Normalize assets to the output dimensions, frame rate, and audio format as needed.

### Image/banner advertisements

- Accept PNG, JPG, and WEBP assets.
- Overlay the image on the main video without interrupting it.
- Configure duration, size, position, opacity, and fade in/out.
- Preserve source audio and avoid unreadable subtitle overlap through preview and placement controls.

## Scope boundaries

The planned workflow includes local processing, review, an advertisement library, an export queue, and later Windows distribution. Automatic social publishing, cloud processing, paid AI services, and ad asset generation are outside the initial scope. The implemented application supports source video selection, local transcription/persistence, configurable LLM providers, chunked candidate analysis, and source-interval review with editable boundaries, selection, explicit approval, and project save/reload. Rendering and later workflows remain planned.
