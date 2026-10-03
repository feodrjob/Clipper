# Goal
Let users select a source video and inspect its metadata.

# Requirements
- Add file selection and service-based metadata loading.
- Display path, duration, dimensions, frame rate, and audio availability.
- Handle unsupported, missing, or unreadable files without blocking the UI.

# Acceptance Criteria
- A valid source becomes the current project source with metadata.
- Invalid input produces a useful error and does not replace a valid source.
- Import leaves the source unchanged.

# Dependencies
- US-001, US-003. Implement US-003 before completing this story.

# Tests / Definition of Done
- Test valid/invalid metadata and selection state using a fake probe.
- Verify import with a small media fixture and manually check file selection.
