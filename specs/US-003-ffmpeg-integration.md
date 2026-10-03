# Goal
Provide reliable FFmpeg and FFprobe access behind a service boundary.

# Requirements
- Discover configurable executables and report missing tools.
- Parse probe metadata and execute argument lists with progress/error capture.
- Support cancellation and isolated temporary output cleanup.

# Acceptance Criteria
- Metadata is normalized into domain types.
- Failed and cancelled commands never appear successful.
- Paths containing spaces work; original files remain intact.

# Dependencies
- US-001.

# Tests / Definition of Done
- Test discovery, metadata parsing, and process errors with fakes.
- Run small-media probe/transcode and cancellation integration checks when tools are available.
