# Goal
Insert a selected video advertisement into a clip.

# Requirements
- Choose an insertion point and normalize the ad to the output format.
- Play ad audio during insertion; resume source video/audio afterward.
- Shift subsequent subtitle timings and suppress source captions during the ad.

# Acceptance Criteria
- Final duration equals source clip duration plus inserted ad duration within encoding tolerance.
- Source resumes at the insertion point without skipped speech or audio mixing during the ad.
- Silent ads and ads of different durations are supported.

# Dependencies
- US-008, US-009, US-010.

# Tests / Definition of Done
- Test timeline mapping at start, middle, and end insertion points.
- Render fixtures with audible/silent ads; inspect transitions, durations, and caption sync.
