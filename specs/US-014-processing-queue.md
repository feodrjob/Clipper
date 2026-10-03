# Goal
Manage multiple processing/export jobs without freezing the application.

# Requirements
- Add a visible sequential queue with queued/running/completed/failed/cancelled states.
- Show per-job progress; cancel queued or active work and retry failures explicitly.
- Persist job metadata and mark interrupted jobs after restart; do not imply automatic stage resume.

# Acceptance Criteria
- Heavy jobs run sequentially and GUI controls remain responsive.
- One failed/cancelled job does not corrupt other jobs or source files.
- Restart exposes interrupted jobs for explicit retry with clear output handling.

# Dependencies
- US-004, US-006, US-013.

# Tests / Definition of Done
- Test state transitions, scheduling, cancellation, retry, and restart recovery with fake workers.
- Manually verify responsiveness and cancellation during a small export batch.
