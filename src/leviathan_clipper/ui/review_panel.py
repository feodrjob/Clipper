"""Review, edit and approve candidates; no video processing commands."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView, QDoubleSpinBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from leviathan_clipper.domain.clips import QUALITY_NAMES
from leviathan_clipper.video.preview import IntervalPreview


class ReviewPanel(QWidget):
    selected = Signal(str, bool)
    edited = Signal(str, float, float)
    approve_requested = Signal()
    save_requested = Signal()
    load_requested = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        layout = QVBoxLayout(self)
        self.summary = QLabel("Analyze a transcript or load a review project.")
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Use", "Start (s)", "End (s)", "Duration", "Title", "Score"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemChanged.connect(self._checked)
        self.table.currentCellChanged.connect(self._current)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.video = QVideoWidget()
        self.video.setMinimumSize(160, 90)
        self.preview = IntervalPreview(self.video, self)
        self.preview.status.connect(self._preview_status)
        self.preview.failed.connect(self._preview_failed)
        self.preview.position.connect(self._preview_position)
        self.preview_label = QLabel("Preview stopped.")
        self.preview_label.setTextFormat(Qt.TextFormat.PlainText)
        self.start_field, self.end_field = QDoubleSpinBox(), QDoubleSpinBox()
        for field in (self.start_field, self.end_field):
            field.setDecimals(2)
            field.setSingleStep(0.1)
        self.duration_label = QLabel("Duration: —")
        self.apply_button = QPushButton("Apply boundaries")
        self.apply_button.clicked.connect(self._edit)
        self.play_button = QPushButton("Preview clip")
        self.play_button.clicked.connect(self.play_current)
        self.stop_button = QPushButton("Stop preview")
        self.stop_button.clicked.connect(self.stop_preview)
        self.approve_button = QPushButton("Use selected clips")
        self.approve_button.clicked.connect(self.approve_requested.emit)
        self.save_button = QPushButton("Save review project…")
        self.save_button.clicked.connect(self.save_requested.emit)
        self.load_button = QPushButton("Load review project…")
        self.load_button.clicked.connect(self.load_requested.emit)
        lower = QHBoxLayout()
        lower.addWidget(self.details, 1)
        lower.addWidget(self.video, 1)
        edit = QHBoxLayout()
        for widget in (QLabel("Start"), self.start_field, QLabel("End"), self.end_field,
                       self.duration_label, self.apply_button, self.play_button, self.stop_button):
            edit.addWidget(widget)
        actions = QHBoxLayout()
        for widget in (self.approve_button, self.save_button, self.load_button):
            actions.addWidget(widget)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 2)
        layout.addLayout(lower, 1)
        layout.addWidget(self.preview_label)
        layout.addLayout(edit)
        layout.addLayout(actions)
        self.set_project(None)

    def set_project(self, project):
        current_id = self.current_id()
        self.project = project
        self.table.blockSignals(True)
        candidates = project.candidates if project is not None else ()
        self.table.setRowCount(len(candidates))
        selected_row = 0
        for row, candidate in enumerate(candidates):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            check.setData(Qt.ItemDataRole.UserRole, candidate.id)
            check.setCheckState(Qt.CheckState.Checked if candidate.id in project.selected_ids else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            for column, value in enumerate((f"{candidate.start:.2f}", f"{candidate.end:.2f}", f"{candidate.duration:.2f}",
                                             candidate.title, f"{candidate.score:g}/100"), 1):
                self.table.setItem(row, column, QTableWidgetItem(value))
            if candidate.id == current_id:
                selected_row = row
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)
        self.summary.setText(f"{len(project.selected_ids)} selected · {len(project.approved_ids)} approved" if project else
                             "Analyze a transcript or load a review project.")
        for field in (self.start_field, self.end_field):
            field.setRange(0, project.source.duration if project else 0)
        if candidates:
            self.table.setCurrentCell(selected_row, 0)
            self._current()
        else:
            self.details.clear()
            self.duration_label.setText("Duration: —")
        for button in (self.play_button, self.apply_button):
            button.setEnabled(bool(candidates))
        self.approve_button.setEnabled(project is not None and bool(project.selected_ids))
        self.save_button.setEnabled(project is not None)

    def current_id(self):
        item = self.table.item(self.table.currentRow(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def current_candidate(self):
        return next((c for c in self.project.candidates if c.id == self.current_id()), None) if self.project else None

    def _checked(self, item):
        if item.column() == 0:
            self.selected.emit(item.data(Qt.ItemDataRole.UserRole), item.checkState() == Qt.CheckState.Checked)

    def _current(self, *args):
        candidate = self.current_candidate()
        if candidate is not None:
            self.start_field.setValue(candidate.start)
            self.end_field.setValue(candidate.end)
            self.duration_label.setText(f"Duration: {candidate.duration:.2f} s")
            quality = ", ".join(f"{name}: {score}/5" for name, score in zip(QUALITY_NAMES, candidate.quality))
            self.details.setPlainText(f"{candidate.title}\nScore: {candidate.score:g}/100 (advisory)\n{candidate.reason}\n{quality}\n\n{candidate.text}")

    def _edit(self):
        if self.current_id() is not None:
            self.stop_preview()
            self.edited.emit(self.current_id(), self.start_field.value(), self.end_field.value())

    def play_current(self):
        candidate = self.current_candidate()
        if candidate is not None:
            self.preview.play(self.project.source, candidate.start, candidate.end)

    def stop_preview(self):
        self.preview.stop()
        self.preview_label.setText("Preview stopped.")

    def _preview_status(self, message):
        self.preview_label.setText(message)

    def _preview_failed(self, message):
        self.preview_label.setText(message)
        self.error.emit(message)

    def _preview_position(self, seconds):
        self.preview_label.setText(f"Source position: {seconds:.2f} s")
