# Goal
Add readable, synchronized subtitles to selected clips.

# Requirements
- Generate ASS from transcript segments with configurable styling.
- Trim/rebase timing through the render timeline and escape subtitle text.
- Burn subtitles through the video layer; allow disabling them.

# Acceptance Criteria
- Text stays within the frame and follows the selected speech.
- Clip boundaries exclude unrelated transcript text.
- Disabled subtitles produce no visible captions.

# Dependencies
- US-004, US-008.

# Tests / Definition of Done
- Test timing, clipping, Unicode, multiline text, and ASS escaping.
- Visually inspect a captioned fixture and verify timing against audio.
