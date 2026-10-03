# Goal
Render reviewed intervals as vertical 9:16 clips.

# Requirements
- Add configurable output resolution and fallback crop/padding.
- Add face-aware tracking where viable, with smoothing and confidence-based fallback.
- Preserve audio synchronization and report rendering progress/errors.

# Acceptance Criteria
- Selected intervals render at the requested 9:16 dimensions.
- Missing, unreliable, or multiple-face tracking produces usable fallback output.
- Original sources are unchanged and failed renders are not finalized.

# Dependencies
- US-003, US-007.

# Tests / Definition of Done
- Test crop bounds, tracking transitions, and fallback decisions using synthetic detections.
- Inspect small rendered fixtures for dimensions, duration, framing, and audio sync.
