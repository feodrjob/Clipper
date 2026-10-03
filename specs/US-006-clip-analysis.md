# Goal
Find and select promising moments from a timestamped transcript.

# Requirements
- Chunk with bounded context and overlap; preserve source timestamps.
- Generate candidates, validate bounds/duration, deduplicate, and optionally rank in a second pass.
- Respect configured clip count and duration bounds; retain reasons/scores for review.

# Acceptance Criteria
- Long transcripts are analyzed without one unbounded request.
- Valid selections map back to source intervals; duplicates and invalid candidates are excluded.
- Insufficient suitable moments return fewer results with an explanation.

# Dependencies
- US-004, US-005.

# Tests / Definition of Done
- Test chunk boundaries, timestamp mapping, invalid JSON, overlaps, ranking, and insufficient results with fake providers.
- Verify deterministic selection behavior on a representative transcript fixture.
