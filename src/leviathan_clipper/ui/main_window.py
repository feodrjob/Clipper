"""Video selection UI; expensive operations run through services/workers."""

import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QLabel, QLineEdit, QMainWindow,
    QPlainTextEdit, QProgressBar, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)
from leviathan_clipper.application.tasks import TaskWorker
from leviathan_clipper.domain.transcript import TranscriptionSettings
from leviathan_clipper.ui.provider_panel import ProviderPanel
from leviathan_clipper.ui.analysis_panel import AnalysisPanel
from leviathan_clipper.ui.review_panel import ReviewPanel
from leviathan_clipper.domain.review import ReviewError
from leviathan_clipper.domain.clips import AnalysisResult


class MainWindow(QMainWindow):
    def __init__(self, import_service, transcription_service=None, provider_service=None, analysis_service=None, review_service=None):
        super().__init__()
        self.import_service = import_service
        self.transcription_service = transcription_service
        self.provider_service = provider_service
        self.analysis_service = analysis_service
        self.analysis_result = None
        self.review_service = review_service
        self.review_project = None
        self.approved_clips = ()
        self.transcript = None
        self.worker = None
        self._closing = False
        self.setWindowTitle("LeviathanClipper")
        self.resize(960, 640)
        content = QWidget()
        layout = QVBoxLayout(content)
        self.title = QLabel("LeviathanClipper")
        self.import_button = QPushButton("Import video…")
        self.import_button.clicked.connect(self.choose_video)
        self.metadata = QLabel("No video selected.")
        self.metadata.setTextFormat(Qt.TextFormat.PlainText)
        self.metadata.setWordWrap(True)
        self.status = QLabel("Ready.")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_task)
        for widget in (self.title, self.import_button, self.metadata, self.status,
                       self.progress_bar, self.cancel_button):
            layout.addWidget(widget)
        form = QFormLayout()
        self.model_field = QLineEdit(os.environ.get("LEVIATHAN_WHISPER_MODEL", "tiny"))
        self.model_field.setPlaceholderText("Downloaded model name or local model folder")
        self.device_field = QComboBox()
        self.device_field.addItems(["cpu", "cuda", "auto"])
        self.precision_field = QComboBox()
        self.precision_field.addItems(["int8", "float32", "float16", "default"])
        self.language_field = QLineEdit()
        self.language_field.setPlaceholderText("Auto-detect (or en, ru, …)")
        form.addRow("Whisper model", self.model_field)
        form.addRow("Device", self.device_field)
        form.addRow("Precision", self.precision_field)
        form.addRow("Language", self.language_field)
        layout.addLayout(form)
        self.transcribe_button = QPushButton("Transcribe locally")
        self.transcribe_button.clicked.connect(self.transcribe_video)
        self.save_button = QPushButton("Save transcript…")
        self.save_button.clicked.connect(self.save_transcript)
        self.load_button = QPushButton("Load transcript…")
        self.load_button.clicked.connect(self.load_transcript)
        self.transcript_view = QPlainTextEdit()
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setPlaceholderText("Timestamped transcript will appear here.")
        for widget in (self.transcribe_button, self.save_button, self.load_button, self.transcript_view):
            layout.addWidget(widget)
        self.provider_panel = None
        if provider_service is not None:
            self.provider_panel = ProviderPanel(provider_service.provider_names, provider_service.defaults())
            self.provider_panel.test_requested.connect(self.test_provider)
            self.provider_panel.error.connect(self._failed)
        self.pages = QTabWidget()
        self.pages.addTab(content, "Video & transcript")
        if self.provider_panel is not None:
            self.pages.addTab(self.provider_panel, "LLM provider")
        self.analysis_panel = None
        if analysis_service is not None:
            self.analysis_panel = AnalysisPanel()
            self.analysis_panel.requested.connect(self.analyze_transcript)
            self.analysis_panel.error.connect(self._failed)
            self.pages.addTab(self.analysis_panel, "Clip analysis")
        self.review_panel = None
        if review_service is not None:
            self.review_panel = ReviewPanel()
            self.review_panel.selected.connect(self.select_clip)
            self.review_panel.edited.connect(self.edit_clip)
            self.review_panel.approve_requested.connect(self.approve_clips)
            self.review_panel.save_requested.connect(self.save_review)
            self.review_panel.load_requested.connect(self.load_review)
            self.review_panel.error.connect(self._failed)
            self.pages.addTab(self.review_panel, "Clip review")
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(self.pages)
        for widget in (self.status, self.progress_bar, self.cancel_button):
            layout.removeWidget(widget)
            root_layout.addWidget(widget)
        self._update_controls()
        self.setCentralWidget(root)

    def choose_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import video", "", "Video files (*.mp4 *.mkv *.mov *.avi *.webm *.m4v);;All files (*)",
        )
        if path:
            self.import_video(path)

    def import_video(self, path):
        self.start_task(
            lambda cancel, progress: self.import_service.inspect(path, cancel, progress),
            self._imported,
        )

    def start_task(self, operation, on_success):
        if self.worker is not None:
            return
        if self.review_panel is not None:
            self.review_panel.stop_preview()
        self.worker = TaskWorker(operation, self)
        self.worker.succeeded.connect(on_success)
        self.worker.failed.connect(self._failed)
        self.worker.cancelled.connect(self._cancelled)
        self.worker.progress.connect(self._progress)
        self.worker.finished.connect(self._finished)
        self.import_button.setEnabled(False)
        self._update_controls(busy=True)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setRange(0, 0)
        self.status.setText("Working…")
        self.worker.start()

    def _imported(self, media):
        self.import_service.select(media)
        self.transcript = None
        self.transcript_view.clear()
        self.clear_analysis()
        rate = f"{media.frame_rate:.3f} fps" if media.frame_rate is not None else "Unknown frame rate"
        self.metadata.setText(
            f"Path: {media.path}\nDuration: {media.duration:.2f} seconds\n"
            f"Dimensions: {media.width} × {media.height}\nFrame rate: {rate}\n"
            f"Audio: {'Yes' if media.has_audio else 'No'}"
        )
        self.status.setText("Video imported.")

    def _failed(self, message):
        self.status.setText(f"Error: {message}")

    def _cancelled(self):
        self.status.setText("Operation cancelled.")

    def _progress(self, fraction, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(round(max(0, min(1, fraction)) * 100))
        self.status.setText(message)

    def cancel_task(self):
        if self.worker is not None:
            self.worker.cancel()
            self.status.setText("Cancelling…")

    def _finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.import_button.setEnabled(True)
        self._update_controls()
        self.cancel_button.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        if self._closing:
            self.close()

    def _update_controls(self, busy=False):
        source = self.import_service.state.source
        available = self.transcription_service is not None and not busy
        self.transcribe_button.setEnabled(available and source is not None and source.has_audio)
        self.load_button.setEnabled(available and source is not None)
        self.save_button.setEnabled(available and self.transcript is not None)
        for field in (self.model_field, self.device_field, self.precision_field, self.language_field):
            field.setEnabled(not busy)
        if self.provider_panel is not None:
            self.provider_panel.setEnabled(not busy)
        if self.analysis_panel is not None:
            self.analysis_panel.setEnabled(not busy)
            self.analysis_panel.button.setEnabled(not busy and self.transcript is not None and bool(self.transcript.segments))
        if self.review_panel is not None:
            self.review_panel.setEnabled(not busy)

    def test_provider(self, config):
        self.start_task(
            lambda cancel, progress: self.provider_service.test_connection(config, cancel, progress),
            self._provider_tested,
        )

    def _provider_tested(self, result):
        self.status.setText(result)

    def transcribe_video(self):
        source = self.import_service.state.source
        if source is None or self.transcription_service is None:
            return
        try:
            settings = TranscriptionSettings(
                self.model_field.text().strip(), self.device_field.currentText(),
                self.language_field.text().strip() or None, self.precision_field.currentText(),
            )
        except ValueError as exc:
            self._failed(str(exc))
            return
        self.start_task(
            lambda cancel, progress: self.transcription_service.generate(source, settings, cancel, progress),
            self._transcribed,
        )

    def _transcribed(self, transcript):
        self.transcript = transcript
        self.clear_analysis()
        self.transcript_view.setPlainText("\n".join(
            f"[{s.start:.2f}–{s.end:.2f}] {s.text}" for s in transcript.segments
        ))
        self.status.setText(f"Transcript ready: {len(transcript.segments)} segments ({transcript.language})."
                            if transcript.segments else "No speech detected.")

    def clear_analysis(self):
        self.analysis_result = None
        if self.analysis_panel is not None:
            self.analysis_panel.summary.clear()
        self.review_project = None
        self.approved_clips = ()
        if self.review_panel is not None:
            self.review_panel.stop_preview()
            self.review_panel.set_project(None)

    def analyze_transcript(self, settings):
        if self.transcript is None or self.analysis_service is None or self.provider_panel is None:
            return
        try:
            config = self.provider_panel.configuration()
        except ValueError as exc:
            self._failed(str(exc))
            return
        transcript = self.transcript
        self.start_task(
            lambda cancel, progress: self.analysis_service.generate(transcript, config, settings, cancel, progress),
            self._analyzed,
        )

    def _analyzed(self, result):
        self.analysis_result = result
        self.analysis_panel.show_result(result)
        self.status.setText(f"Analysis complete: {len(result.suggested_ids)} suggested clips."
                            + (" See analysis warnings." if result.warnings else ""))
        if self.review_service is not None:
            self._set_review(self.review_service.begin(self.import_service.state.source, self.transcript, result))
            self.pages.setCurrentWidget(self.review_panel)

    def _set_review(self, project):
        self.review_project = project
        self.approved_clips = project.approved_clips
        self.review_panel.set_project(project)

    def select_clip(self, id, selected):
        if self.review_project is not None:
            try:
                self._set_review(self.review_service.select(self.review_project, id, selected))
                self.status.setText("Selection changed. Use selected clips to approve it.")
            except ReviewError as exc:
                self._failed(str(exc))

    def edit_clip(self, id, start, end):
        if self.review_project is not None:
            try:
                self._set_review(self.review_service.edit(self.review_project, id, start, end))
                self.status.setText("Boundaries updated. Check context and approve the selection again.")
            except ReviewError as exc:
                self._failed(str(exc))

    def approve_clips(self):
        if self.review_project is not None:
            try:
                self._set_review(self.review_service.approve(self.review_project))
                self.approved_clips = self.review_service.approved_selection(self.review_project)
                self.status.setText(f"Approved {len(self.approved_clips)} selected clips.")
            except ReviewError as exc:
                self._failed(str(exc))

    def save_review(self):
        if self.review_project is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save review project", "review.json", "JSON files (*.json)")
        if path:
            project = self.review_project
            self.start_task(lambda cancel, progress: self.review_service.save(project, path, cancel, progress), self._review_saved)

    def _review_saved(self, path):
        self.status.setText(f"Review project saved: {path}")

    def load_review(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load review project", "", "JSON files (*.json)")
        if path:
            self.start_task(lambda cancel, progress: self.review_service.load(path, cancel, progress), self._review_loaded)

    def _review_loaded(self, project):
        self._imported(project.source)
        self._transcribed(project.transcript)
        self.analysis_result = AnalysisResult(project.candidates, project.selected_ids, (), len(project.selected_ids))
        if self.analysis_panel is not None:
            self.analysis_panel.show_result(self.analysis_result)
        self._set_review(project)
        self.pages.setCurrentWidget(self.review_panel)
        self.status.setText(f"Review loaded: {len(project.selected_ids)} selected, {len(project.approved_ids)} approved.")

    def save_transcript(self):
        if self.transcript is None or self.transcription_service is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save transcript", "transcript.json", "JSON files (*.json)")
        if path:
            transcript = self.transcript
            self.start_task(
                lambda cancel, progress: self.transcription_service.save(transcript, path, cancel, progress),
                self._saved,
            )

    def _saved(self, path):
        self.status.setText(f"Transcript saved: {path}")

    def load_transcript(self):
        source = self.import_service.state.source
        if source is None or self.transcription_service is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load transcript", "", "JSON files (*.json)")
        if path:
            self.start_task(
                lambda cancel, progress: self.transcription_service.load(source, path, cancel, progress),
                self._transcribed,
            )

    def closeEvent(self, event):
        if self.review_panel is not None:
            self.review_panel.stop_preview()
        if self.worker is not None:
            self._closing = True
            self.cancel_task()
            event.ignore()
        else:
            event.accept()
