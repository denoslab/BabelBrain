"""
The Federated Learning tab of Advanced Options, BB-04.

Users opt in, see what the local sample store holds, and delete samples.
Off by default. The explanation text is a draft for Samuel to review.
"""

import json
import os
import urllib.error
import urllib.request

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QRadioButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import FL_COLLECT, FL_OFF, FL_TRAIN, schema
from .store import SampleStore

LEVEL_LABELS = {
    FL_OFF: "Off",
    FL_COLLECT: "Collect samples locally",
    FL_TRAIN: "Collect samples and take part in training",
}
# Local status endpoint of the FL participant app, SF-08. Placeholder until that app exists.
CLIENT_STATUS_URL = 'http://127.0.0.1:8765/status'
CLIENT_TIMEOUT_S = 0.3


def client_status(url=CLIENT_STATUS_URL):
    """One line about the FL client: 'not installed' when nothing answers locally."""
    try:
        with urllib.request.urlopen(url, timeout=CLIENT_TIMEOUT_S) as response:
            status = json.loads(response.read().decode())
    except (urllib.error.URLError, OSError, ValueError):
        return "FL client: not installed or not running"
    if not isinstance(status, dict):
        return "FL client: unexpected status"
    parts = ["enrolled" if status.get('enrolled') else "not enrolled"]
    if status.get('current_round'):
        parts.append("round {}".format(status['current_round']))
    if status.get('global_model_version'):
        parts.append("model {}".format(status['global_model_version']))
    return "FL client: " + ", ".join(parts)


class FLSettingsWidget(QWidget):
    """Level selector, store folder, store overview and sample review."""

    def __init__(self, parent=None, current_level=FL_OFF, store_folder=''):
        super(FLSettingsWidget, self).__init__(parent)
        self._build()
        self.set_level(current_level)
        self.set_store_folder(store_folder)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        intro = QLabel(
            "Federated learning lets BabelBrain labs improve a fast ultrasound model together "
            "without sharing data. When it is on, BabelBrain saves one training sample on this "
            "computer after each successful Step 2 run with a real CT: the CT crop, the water and "
            "transcranial fields, and tissue maps. <b>Samples never leave this computer.</b> "
            "Only model weights trained on them are shared, and only if you choose to take "
            "part in training. No names, file names, paths, exact dates or MRI images are saved; only the month of export is kept. "
            "This is <b>off by default</b>.")
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        layout.addWidget(intro)

        self._group = QButtonGroup(self)
        self._buttons = {}
        for level in (FL_OFF, FL_COLLECT, FL_TRAIN):
            button = QRadioButton(LEVEL_LABELS[level])
            self._group.addButton(button, level)
            self._buttons[level] = button
            layout.addWidget(button)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Sample store:"))
        self._folder = QLineEdit()
        self._folder.setPlaceholderText(schema.DEFAULT_STORE)
        self._folder.editingFinished.connect(self.refresh)
        folder_row.addWidget(self._folder, 1)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        folder_row.addWidget(browse)
        layout.addLayout(folder_row)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Sample ID", "Frequency", "Split", "Month"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table, 1)

        buttons = QHBoxLayout()
        self._delete = QPushButton("Delete selected samples")
        self._delete.clicked.connect(self.delete_selected)
        buttons.addWidget(self._delete)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._client = QLabel()
        layout.addWidget(self._client)

    # --------------------------------------------------
    # Values saved with the Advanced Options
    # --------------------------------------------------

    def selected_level(self):
        level = self._group.checkedId()
        return FL_OFF if level == -1 else level

    def set_level(self, level):
        if level not in self._buttons:
            level = FL_OFF
        self._buttons[level].setChecked(True)

    def store_folder(self):
        return self._folder.text().strip()

    def set_store_folder(self, folder):
        self._folder.setText(folder or '')
        self.refresh()

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Sample store folder",
                                                  self.store_folder() or os.path.expanduser('~'))
        if folder:
            self.set_store_folder(folder)

    # --------------------------------------------------
    # Store overview and review
    # --------------------------------------------------

    def _store(self):
        return SampleStore(self.store_folder() or None)

    def refresh(self):
        try:
            store = self._store()
            summary = store.summary()
            entries = store.entries()
        except Exception:
            self._summary.setText("The sample store cannot be read.")
            self._table.setRowCount(0)
            return
        per_bucket = {}
        for (bucket, split), n in summary['counts'].items():
            per_bucket.setdefault(bucket, {})[split] = n
        lines = []
        for bucket in sorted(b for b in per_bucket if b is not None):
            counts = per_bucket[bucket]
            lines.append("{} kHz: {} train, {} val".format(
                bucket // 1000, counts.get('train', 0), counts.get('val', 0)))
        text = "Samples: " + ("; ".join(lines) if lines else "none")
        text += ". Disk use: {:.1f} MB.".format(summary['bytes'] / 1e6)
        outcomes = {k: v for k, v in summary['outcomes'].items() if k != 'exported'}
        if outcomes:
            text += " Runs not saved, by reason: " + ", ".join(
                "{} {}".format(k.replace('_', ' '), v) for k, v in sorted(outcomes.items())) + "."
        self._summary.setText(text)

        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [entry.get('sample_id', ''), "{} kHz".format(int(entry.get('bucket_hz', 0)) // 1000),
                      entry.get('split', ''), entry.get('exported_month', '')]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(str(value)))
        self._client.setText(client_status())

    def selected_sample_ids(self):
        rows = sorted({index.row() for index in self._table.selectedIndexes()})
        return [self._table.item(row, 0).text() for row in rows]

    def delete_selected(self):
        ids = self.selected_sample_ids()
        if not ids:
            return
        answer = QMessageBox.question(
            self, "Delete samples",
            "Delete {} sample(s) from this computer? This cannot be undone.".format(len(ids)))
        if answer != QMessageBox.Yes:
            return
        store = self._store()
        for sample_id in ids:
            store.delete(sample_id)
        self.refresh()
