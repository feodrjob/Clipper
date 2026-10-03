"""Configuration widgets with no endpoint calls."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QLineEdit, QPushButton, QSpinBox, QWidget
from leviathan_clipper.llm.contracts import ProviderConfig


class ProviderPanel(QWidget):
    test_requested = Signal(object)
    error = Signal(str)

    def __init__(self, provider_names, defaults, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        self.provider = QComboBox()
        self.provider.addItems(provider_names)
        configured = defaults.get("provider", "")
        if configured and configured not in provider_names:
            self.provider.addItem(configured)
        self.provider.setCurrentText(configured)
        self.endpoint = QLineEdit(defaults.get("endpoint", ""))
        self.model = QLineEdit(defaults.get("model", ""))
        self.model.setPlaceholderText("Installed model name (configured by you)")
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(1, 600)
        self.timeout.setValue(120)
        self.context = QSpinBox()
        self.context.setRange(2048, 32768)
        self.context.setValue(8192)
        self.output = QSpinBox()
        self.output.setRange(64, 4096)
        self.output.setValue(1024)
        self.mode = QComboBox()
        self.mode.addItems(["schema", "json"])
        self.test_button = QPushButton("Test connection and structured output")
        self.test_button.clicked.connect(self.request_test)
        for label, widget in (("Provider", self.provider), ("Endpoint", self.endpoint), ("Model", self.model),
                              ("Timeout (seconds)", self.timeout), ("Context tokens", self.context),
                              ("Output tokens", self.output), ("Output mode", self.mode), ("", self.test_button)):
            form.addRow(label, widget)

    def configuration(self):
        return ProviderConfig(self.provider.currentText(), self.endpoint.text().strip(), self.model.text().strip(),
                              self.timeout.value(), self.context.value(), self.output.value(), self.mode.currentText())

    def request_test(self):
        try:
            self.test_requested.emit(self.configuration())
        except ValueError as exc:
            self.error.emit(str(exc))
