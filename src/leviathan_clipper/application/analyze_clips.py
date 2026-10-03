"""Analysis entry point without model/runtime-specific logic."""

class AnalysisService:
    def __init__(self, analyzer):
        self.analyzer = analyzer

    def generate(self, transcript, config, settings, cancel, progress):
        return self.analyzer.analyze(transcript, config, settings, cancel, progress)
