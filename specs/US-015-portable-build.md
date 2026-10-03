# Goal
Package the application for Windows without requiring a Python development setup.

# Requirements
- Add a repeatable PyInstaller build and documented launch/setup instructions.
- Define FFmpeg distribution/discovery and license notices.
- Keep large AI models and local LLM runtimes separately provisioned, with configurable paths and diagnostics.
- Verify writable user-data/temp locations independently of the executable directory.

# Acceptance Criteria
- Build launches on a clean supported Windows machine without installed Python.
- Missing FFmpeg, models, or Ollama produces actionable setup guidance.
- After local prerequisites are provisioned, the complete workflow runs without paid AI APIs.

# Dependencies
- US-001 through US-014; a documented supported Windows/hardware baseline.

# Tests / Definition of Done
- Build and smoke-test on clean Windows, including paths with spaces and Unicode.
- Run a small offline end-to-end fixture with prerequisites present and verify failure diagnostics without them.
- Record packaging limitations and third-party redistribution/license decisions.
