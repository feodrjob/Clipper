# Goal
Let users review and adjust proposed clips before rendering.

# Requirements
- Show candidates with text, timing, and selection reasons.
- Preview source intervals; select/deselect and edit clip boundaries.
- Persist approved selections and reject invalid intervals.

# Acceptance Criteria
- Only approved selections enter rendering.
- Boundary edits remain inside source bounds and update displayed duration.
- Reviewed selections survive project reload.

# Dependencies
- US-002, US-006.

# Tests / Definition of Done
- Test interval validation and selection persistence.
- Verify preview, boundary editing, and selection controls in the GUI.
