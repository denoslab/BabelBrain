"""Tests for the Federated Learning tab, BB-04. Needs PySide6 and pytest-qt; synthetic data only."""

import ast
import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
pytest.importorskip('pytestqt')

from PySide6.QtWidgets import QMessageBox  # noqa: E402

from FederatedLearning import FL_COLLECT, FL_OFF, FL_TRAIN, synthetic  # noqa: E402
from FederatedLearning.SettingsWidget import FLSettingsWidget, client_status  # noqa: E402
from FederatedLearning.exporter import export_from_step2  # noqa: E402
from FederatedLearning.store import SampleStore  # noqa: E402

BABELBRAIN_DIR = Path(__file__).resolve().parents[2]


def filled_store(tmp_path, n=3):
    root = str(tmp_path / 'store')
    for i in range(n):
        subject = str(tmp_path / 'studies' / 'subject{}'.format(i))
        full, water = synthetic.fake_step2_outputs(subject, seed=i + 1)
        export_from_step2(full, water, synthetic.run_info(subject), store_root=root,
                          crop=synthetic.fake_crop())
    export_from_step2(full, water, synthetic.run_info(subject, CTType=2), store_root=root)
    return root


def test_default_is_off(qtbot):
    widget = FLSettingsWidget()
    qtbot.addWidget(widget)
    assert widget.selected_level() == FL_OFF


def test_level_and_folder_round_trip(qtbot, tmp_path):
    widget = FLSettingsWidget(current_level=FL_TRAIN, store_folder=str(tmp_path))
    qtbot.addWidget(widget)
    assert widget.selected_level() == FL_TRAIN
    widget.set_level(FL_COLLECT)
    assert widget.selected_level() == FL_COLLECT
    widget.set_level(42)
    assert widget.selected_level() == FL_OFF
    assert widget.store_folder() == str(tmp_path)


def test_overview_shows_counts_and_reasons(qtbot, tmp_path):
    widget = FLSettingsWidget(store_folder=filled_store(tmp_path))
    qtbot.addWidget(widget)
    assert widget._table.rowCount() == 3
    text = widget._summary.text()
    assert '250 kHz' in text and 'not real ct 1' in text


def test_delete_removes_the_file_and_starfish_no_longer_sees_it(qtbot, tmp_path):
    root = filled_store(tmp_path)
    widget = FLSettingsWidget(store_folder=root)
    qtbot.addWidget(widget)
    widget._table.selectRow(0)
    doomed = widget.selected_sample_ids()
    with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
        widget.delete_selected()
    assert widget._table.rowCount() == 2
    remaining = {e['sample_id'] for e in SampleStore(root).entries()}
    assert doomed[0] not in remaining
    assert not list(Path(root, 'v1', '250000').glob(doomed[0] + '.h5'))

    reader = next((p / 'starfish-fl' / 'controller' / 'starfish' / 'controller' / 'tasks'
                   / 'babel_brain_fno' / 'store.py' for p in Path(__file__).resolve().parents
                   if (p / 'starfish-fl').is_dir()), None)
    if reader is not None and reader.is_file() and importlib.util.find_spec('jsonschema'):
        spec = importlib.util.spec_from_file_location('starfish_store', reader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ids = {r.sample_id for r in module.SampleStore(root).samples(250000)}
        assert doomed[0] not in ids and len(ids) == 2


def test_cancelled_delete_keeps_the_sample(qtbot, tmp_path):
    widget = FLSettingsWidget(store_folder=filled_store(tmp_path))
    qtbot.addWidget(widget)
    widget._table.selectRow(0)
    with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
        widget.delete_selected()
    assert widget._table.rowCount() == 3


def test_client_status_without_a_client():
    assert 'not installed' in client_status('http://127.0.0.1:9/status')


def stub_heavy_modules(monkeypatch):
    """Options.py imports calibration, PlanTUS and the FDTD solver; the tab needs none of them."""
    for name, attrs in {
            'Calibration.TxCalibration': ['RUN_FITTING_Process'],
            'Calibration.ViewResults': ['PlotViewerCalibration'],
            'PlanTUSViewer.RunPlanTUS': ['RUN_PLAN_TUS'],
            'BabelViscoFDTD': [], 'BabelViscoFDTD.H5pySimple': ['SaveToH5py', 'ReadFromH5py']}.items():
        module = types.ModuleType(name)
        for attr in attrs:
            setattr(module, attr, lambda *a, **k: None)
        monkeypatch.setitem(sys.modules, name, module)


def test_options_default_and_tab(qtbot, monkeypatch):
    stub_heavy_modules(monkeypatch)
    try:
        from Options.Options import AdvancedOptions, OptionalParams
    except ImportError as e:
        pytest.skip('Options.py needs a module this environment lacks: {}'.format(e))
    defaults = OptionalParams(['Single'])
    assert defaults.FLLevel == FL_OFF and defaults.FLStore == ''
    assert 'FLLevel' in defaults.keys() and 'FLStore' in defaults.keys()
    del AdvancedOptions


def test_fl_settings_do_not_invalidate_step1_caches():
    """ValidParam in BabelBrain.py must leave FLLevel and FLStore out of the Step 1 hash."""
    tree = ast.parse((BABELBRAIN_DIR / 'BabelBrain.py').read_text())
    valid = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'ValidParam')
    excluded = {c.value for n in ast.walk(valid) if isinstance(n, ast.List)
                for c in n.elts if isinstance(c, ast.Constant)}
    assert {'FLLevel', 'FLStore', 'TelemetryLevel'} <= excluded
