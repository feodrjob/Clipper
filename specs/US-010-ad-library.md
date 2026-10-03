# Goal
Manage reusable advertisement presets in a separate library.

# Requirements
- Add, list, preview, edit, and remove video/image presets.
- Store asset references and default placement settings in versioned metadata.
- Validate media types and report missing assets; deletion removes presets without deleting source assets.

# Acceptance Criteria
- Video and PNG/JPG/WEBP presets survive restart and are separately selectable.
- Invalid assets are rejected with useful feedback.
- Selecting a preset enables later placement without automatically modifying every clip.

# Dependencies
- US-002, US-003.

# Tests / Definition of Done
- Test preset CRUD, serialization, format validation, and missing files.
- Verify library preview and selection in the GUI.
