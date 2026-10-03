"""Analysis settings and advisory result summary."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget
from leviathan_clipper.domain.clips import AnalysisSettings


class AnalysisPanel(QWidget):
    requested = Signal(object)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.count = QSpinBox()
        self.count.setRange(1, 50)
        self.count.setValue(5)
        self.minimum = QDoubleSpinBox()
        self.maximum = QDoubleSpinBox()
        for field, value in ((self.minimum, 20), (self.maximum, 60)):
            field.setRange(1, 600)
            field.setValue(value)
        self.budget = QSpinBox()
        self.budget.setRange(512, 12000)
        self.budget.setValue(4000)
        self.overlap = QDoubleSpinBox()
        self.overlap.setRange(0, 60)
        self.overlap.setValue(20)
        self.score = QDoubleSpinBox()
        self.score.setRange(0, 100)
        self.score.setValue(40)
        self.rank = QCheckBox("Optional second-pass ranking (extra local inference)")
        self.button = QPushButton("Analyze transcript")
        self.button.clicked.connect(self.request_analysis)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        for label, field in (("Desired clip count", self.count), ("Minimum duration (s)", self.minimum),
                              ("Maximum duration (s)", self.maximum), ("Chunk UTF-8 bytes", self.budget),
                              ("Chunk overlap (s)", self.overlap), ("Minimum model score", self.score)):
            form.addRow(label, field)
        layout.addLayout(form)
        layout.addWidget(self.rank)
        layout.addWidget(self.button)
        layout.addWidget(self.summary)

    def request_analysis(self):
        try:
            settings = AnalysisSettings(self.count.value(), self.minimum.value(), self.maximum.value(),
                                        self.budget.value(), self.overlap.value(), self.score.value(), self.rank.isChecked())
            self.requested.emit(settings)
        except ValueError as exc:
            self.error.emit(str(exc))

    def show_result(self, result):
        self.summary.setPlainText(
            f"{len(result.suggested_ids)} suggested clips from {len(result.candidates)} unique candidates.\n"
            + "\n".join(f"{c.start:.2f}–{c.end:.2f} · {c.title} · {c.score:g}/100\n{c.reason}" for c in result.suggested)
            + ("\n\n" + "\n".join(result.warnings) if result.warnings else "")
        )
