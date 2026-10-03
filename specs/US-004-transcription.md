# Goal
Generate a reusable timestamped transcript locally.

# Requirements
- Add a faster-whisper adapter with configurable model, device, and language.
- Extract suitable audio through the media layer as needed.
- Persist transcript segments; report progress, cancellation, and model/hardware errors.

# Acceptance Criteria
- Segments retain valid source timestamps and text.
- A saved transcript can be reloaded without transcription.
- Missing audio or models produce actionable errors; processing stays off the GUI thread.

# Dependencies
- US-002, US-003.

# Tests / Definition of Done
- Test segment conversion, persistence, cancellation, and errors with a fake transcriber.
- Run an opt-in local-model smoke check on a short speech fixture.
