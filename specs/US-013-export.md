# Goal
Export reviewed clips as finalized MP4 files.

# Requirements
- Configure destination and output settings; export one or multiple clips.
- Compose framing, optional subtitles, and selected ads through a render plan.
- Use H.264/AAC where audio exists; validate output and handle naming collisions explicitly.

# Acceptance Criteria
- Successful files are playable MP4s with correct dimensions, duration, and synchronized audio/captions.
- Failed/cancelled outputs are not presented as complete.
- Existing files are never silently overwritten.

# Dependencies
- US-008, US-009, US-011, US-012.

# Tests / Definition of Done
- Test render-plan composition, destination validation, naming, and failure cleanup.
- Export multiple small fixtures and verify metadata plus playback.
