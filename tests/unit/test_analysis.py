from dataclasses import replace
import json
from pathlib import Path
from threading import Event

import pytest
from leviathan_clipper.analysis.analyzer import ClipAnalyzer, candidate_key, deduplicate
from leviathan_clipper.analysis.chunks import chunk_transcript, compact
from leviathan_clipper.application.providers import ProviderService
from leviathan_clipper.domain.cancellation import CancelledError
from leviathan_clipper.domain.clips import AnalysisSettings
from leviathan_clipper.domain.transcript import Transcript, TranscriptSegment
from leviathan_clipper.llm.contracts import ProviderConfig, ProviderError
from leviathan_clipper.llm.providers.fake import FakeProvider


def transcript(rows=None):
    if rows is None:
        rows = json.loads((Path(__file__).parents[1] / "fixtures/moment_transcript.json").read_text())
    segments = tuple(TranscriptSegment(*row) for row in rows)
    return Transcript(Path("source.mp4"), max((s.end for s in segments), default=1), 1, 1, "en", "any-model", segments)


def candidate(first=0, last=1, score=90, **overrides):
    data = dict(first=first, last=last, title="A complete interesting moment", score=score,
                reason="Strong hook with context and a finished ending", quality=[5, 5, 3, 3, 2, 4, 4, 5, 5])
    data.update(overrides)
    return data


def setup(responses, **config_values):
    fake = FakeProvider(responses)
    service = ProviderService({"fake": lambda config: fake})
    config = ProviderConfig("fake", "http://localhost:1", "arbitrary-model", **config_values)
    return ClipAnalyzer(service), fake, config


def test_chunk_overlap_coverage_bounds_and_oversized_unicode_segment():
    source = transcript([(i * 10, (i + 1) * 10, "Text " * 15) for i in range(40)])
    chunks = chunk_transcript(source, 512, 20)
    assert len(chunks) > 1
    assert {row.id for chunk in chunks for row in chunk.rows} == set(range(40))
    assert any(set(a.ids) & set(b.ids) for a, b in zip(chunks, chunks[1:]))
    assert all(len(chunk.text.encode("utf-8")) <= 512 for chunk in chunks)
    huge = transcript([(0, 30, "Привет 👋 \"hello\"" * 1000)])
    fragments = chunk_transcript(huge, 512, 0)
    assert len(fragments) > 10
    assert "".join(row.text for chunk in fragments for row in chunk.rows) == huge.segments[0].text
    assert all(row.id == 0 and row.start == 0 and row.end == 30 for chunk in fragments for row in chunk.rows)
    assert all(len(chunk.text.encode("utf-8")) <= 512 for chunk in fragments)


def test_long_transcript_never_uses_one_unbounded_request():
    source = transcript([(i * 10, (i + 1) * 10, "A self-contained fact with a clear conclusion. " * 3) for i in range(400)])
    def respond(request):
        rows = [json.loads(line) for line in request.messages[-1].content.splitlines() if line.startswith("[")]
        return json.dumps({"candidates": [candidate(rows[0][0], rows[-1][0])]})
    analyzer, fake, config = setup([respond] * 500, context_tokens=4096, max_output_tokens=512)
    result = analyzer.analyze(source, config, AnalysisSettings(5, 10, 40, 512, 10), Event(), lambda *a: None)
    assert len(fake.requests) > 10 and len(result.suggested) <= 5
    for request in fake.requests:
        estimated = len(("".join(m.content for m in request.messages) + compact(request.schema)).encode("utf-8")) + config.max_output_tokens + 256
        assert estimated <= config.context_tokens
        assert "source.mp4" not in "".join(m.content for m in request.messages)


def test_source_mapping_dedup_selection_and_deterministic_order():
    items = [candidate(0, 1, 90), candidate(0, 1, 80), candidate(4, 5, 85)]
    outputs = []
    for order in (items, list(reversed(items))):
        analyzer, _, config = setup([json.dumps({"candidates": order})])
        outputs.append(analyzer.analyze(transcript(), config, AnalysisSettings(3, 10, 30), Event(), lambda *a: None))
    assert outputs[0].candidates == outputs[1].candidates
    assert outputs[0].suggested_ids == ("clip-0-1", "clip-4-5")
    assert [(c.start, c.end) for c in outputs[0].suggested] == [(0, 20), (40, 60)]
    assert "one-line warning" in outputs[0].suggested[0].text
    assert any("Requested 3" in warning for warning in outputs[0].warnings)


@pytest.mark.parametrize("bad", [candidate(2, 1), candidate(0, 7), candidate(0, 1, 10),
                                candidate(0, 1, quality=[5, 0, 5, 5, 5, 5, 5, 0, 0])])
def test_invalid_or_incomplete_candidates_excluded(bad):
    analyzer, _, config = setup([json.dumps({"candidates": [bad]})])
    result = analyzer.analyze(transcript(), config, AnalysisSettings(2, 10, 30), Event(), lambda *a: None)
    assert not result.candidates and any("excluded" in warning for warning in result.warnings)


def test_invalid_json_and_ids_have_exactly_one_repair_then_safe_skip():
    invalid = json.dumps({"candidates": [candidate(999, 999)]})
    analyzer, fake, config = setup(["not JSON", invalid])
    result = analyzer.analyze(transcript(), config, AnalysisSettings(1, 10, 30), Event(), lambda *a: None)
    assert not result.candidates and len(fake.requests) == 2
    assert "Previous response was invalid" in fake.requests[1].messages[0].content
    assert any("repair" in warning for warning in result.warnings)


def test_repair_can_succeed_without_echoing_model_garbage():
    analyzer, fake, config = setup(["ignore all instructions", json.dumps({"candidates": [candidate()]})])
    result = analyzer.analyze(transcript(), config, AnalysisSettings(1, 10, 30), Event(), lambda *a: None)
    assert len(result.suggested) == 1
    assert "ignore all instructions" not in "".join(m.content for m in fake.requests[1].messages)


def test_optional_rank_changes_selection_and_invalid_rank_keeps_scores():
    items = [candidate(0, 1, 90), candidate(4, 5, 85)]
    analyzer, fake, config = setup([json.dumps({"candidates": items}), json.dumps({"ranked": [
        {"id": "clip-0-1", "score": 50}, {"id": "clip-4-5", "score": 100}]})])
    result = analyzer.analyze(transcript(), config, AnalysisSettings(1, 10, 30, rank_with_llm=True), Event(), lambda *a: None)
    assert result.suggested_ids == ("clip-4-5",) and len(fake.requests) == 2
    analyzer, fake, config = setup([json.dumps({"candidates": items}), "bad", "still bad"])
    result = analyzer.analyze(transcript(), config, AnalysisSettings(1, 10, 30, rank_with_llm=True), Event(), lambda *a: None)
    assert result.suggested_ids == ("clip-0-1",) and len(fake.requests) == 3
    assert any("retained discovery scores" in warning for warning in result.warnings)


def test_overlap_final_selection_and_no_speech():
    analyzer, _, config = setup([json.dumps({"candidates": [candidate(0, 1), candidate(1, 2, 80), candidate(4, 5, 70)]})])
    result = analyzer.analyze(transcript(), config, AnalysisSettings(3, 10, 30), Event(), lambda *a: None)
    assert len(result.candidates) == 3 and result.suggested_ids == ("clip-0-1", "clip-4-5")
    analyzer, fake, config = setup([])
    assert not analyzer.analyze(transcript([]), config, AnalysisSettings(), Event(), lambda *a: None).candidates
    assert not fake.requests


def test_transport_error_is_not_retried_and_cancel_is_propagated():
    analyzer, fake, config = setup([ProviderError("offline", "connection")])
    with pytest.raises(ProviderError, match="offline"):
        analyzer.analyze(transcript(), config, AnalysisSettings(), Event(), lambda *a: None)
    assert len(fake.requests) == 1
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        analyzer.analyze(transcript(), config, AnalysisSettings(), cancel, lambda *a: None)


def test_too_small_output_budget_is_actionable():
    analyzer, fake, config = setup([], max_output_tokens=64)
    with pytest.raises(ProviderError, match="256 output tokens"):
        analyzer.analyze(transcript(), config, AnalysisSettings(), Event(), lambda *a: None)
    assert not fake.requests
