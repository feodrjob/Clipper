# Goal
Overlay selected image advertisements on clips.

# Requirements
- Configure final-output start time, duration, size, position, opacity, and fades.
- Support PNG/JPG/WEBP and applicable transparency.
- Validate placement bounds and provide preview alongside subtitles.

# Acceptance Criteria
- Banner appears only during its configured interval, including on timelines containing video ads.
- Size, position, opacity, and fades match the settings.
- Main video and audio continue throughout the overlay.

# Dependencies
- US-008, US-009, US-010, US-011 for combined ad timelines.

# Tests / Definition of Done
- Test placement validation, fade timing, and output-timeline calculations.
- Inspect rendered format/transparency fixtures and subtitle overlap in preview.
