"""Smoke checks for the installed package."""

import subprocess
import sys
import textwrap


def test_package_imports_are_inert(tmp_path):
    script = textwrap.dedent("""
        import importlib
        import sys

        packages = (
            "leviathan_clipper", "leviathan_clipper.ui",
            "leviathan_clipper.application", "leviathan_clipper.domain",
            "leviathan_clipper.transcription", "leviathan_clipper.llm",
            "leviathan_clipper.llm.providers", "leviathan_clipper.analysis",
            "leviathan_clipper.video", "leviathan_clipper.subtitles",
            "leviathan_clipper.advertisements", "leviathan_clipper.persistence",
            "leviathan_clipper.export",
        )
        for package in packages:
            importlib.import_module(package)
        assert "PySide6" not in sys.modules

        importlib.import_module("leviathan_clipper.__main__")
        from PySide6.QtWidgets import QApplication
        assert QApplication.instance() is None
    """)
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
