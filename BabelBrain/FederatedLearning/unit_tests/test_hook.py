"""Tests for the Step 2 hook, BB-02. Synthetic inputs only."""

import ast
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from FederatedLearning import LEVEL_ENV, STORE_ENV, hook, synthetic
from FederatedLearning.store import SampleStore

BABELBRAIN_DIR = Path(__file__).resolve().parents[2]


def fake_app(tmp_path, **config):
    subject = tmp_path / 'studies' / 'Subject_Anonymous_7'
    full, water = synthetic.fake_step2_outputs(str(subject))
    cfg = {'version': '0.8.2\n', 'TxSystem': 'Single', 'bUseCT': True, 'CTType': 1,
           'T1W': str(subject / 'T1W.nii.gz')}
    cfg.update(config)
    return SimpleNamespace(
        Config=cfg, _Frequency=250e3, _BasePPW=9,
        AcSim=SimpleNamespace(_FullSolName=full, _WaterSolName=water),
        CommomAcOptions=lambda: synthetic.run_info('x')['options'])


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(LEVEL_ENV, raising=False)
    monkeypatch.delenv(STORE_ENV, raising=False)


def test_fl_off_by_default_does_nothing(tmp_path):
    with mock.patch('FederatedLearning.exporter.export_from_step2') as export:
        assert hook.on_step2_finished(fake_app(tmp_path)) is None
    export.assert_not_called()


def test_fl_off_imports_nothing_heavy():
    code = ('import sys; from FederatedLearning.hook import on_step2_finished; '
            'from types import SimpleNamespace; '
            'on_step2_finished(SimpleNamespace(Config={})); '
            'heavy = [m for m in ("numpy", "h5py", "FederatedLearning.exporter") if m in sys.modules]; '
            'print(",".join(heavy))')
    env = {k: v for k, v in os.environ.items() if k != LEVEL_ENV}
    out = subprocess.run([sys.executable, '-c', code], cwd=BABELBRAIN_DIR, env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == ''


def test_level_from_the_environment_or_the_saved_setting(monkeypatch):
    assert hook.fl_level({}) == 0
    assert hook.fl_level({'FLLevel': 1}) == 1
    monkeypatch.setenv(LEVEL_ENV, '2')
    assert hook.fl_level({'FLLevel': 0}) == 2
    monkeypatch.setenv(LEVEL_ENV, 'yes')
    assert hook.fl_level({}) == 0
    monkeypatch.setenv(LEVEL_ENV, '9')
    assert hook.fl_level({}) == 0


def test_fl_on_exports_on_a_background_thread(tmp_path, monkeypatch):
    monkeypatch.setenv(LEVEL_ENV, '1')
    monkeypatch.setenv(STORE_ENV, str(tmp_path / 'store'))
    app = fake_app(tmp_path)
    seen = {}

    def fake_export(full, water, run_info, store_root=None, source='live'):
        seen.update(full=full, run_info=run_info, store_root=store_root, source=source,
                    thread=threading.current_thread().name)
        return SimpleNamespace(status='exported', reason='ok')

    with mock.patch('FederatedLearning.exporter.export_from_step2', side_effect=fake_export):
        thread = hook.on_step2_finished(app)
        thread.join(10)
    assert seen['thread'] == 'FLSampleExport'
    assert seen['full'] == app.AcSim._FullSolName and seen['source'] == 'live'
    assert seen['store_root'] == str(tmp_path / 'store')
    info = seen['run_info']
    assert info['babelbrain_version'] == '0.8.2'
    assert info['frequency_hz'] == 250e3 and info['ppw'] == 9 and info['tx_system'] == 'Single'
    assert info['subject_folder'].endswith('Subject_Anonymous_7')


def test_a_failing_exporter_never_reaches_step2(tmp_path, monkeypatch):
    monkeypatch.setenv(LEVEL_ENV, '1')
    errors = []
    monkeypatch.setattr(threading, 'excepthook', lambda args: errors.append(args))
    with mock.patch('FederatedLearning.exporter.export_from_step2', side_effect=RuntimeError('x')):
        thread = hook.on_step2_finished(fake_app(tmp_path))
        thread.join(10)
    assert errors == []


def test_an_unexpected_app_state_is_skipped(monkeypatch):
    monkeypatch.setenv(LEVEL_ENV, '1')
    assert hook.on_step2_finished(SimpleNamespace(Config={})) is None


def test_real_exporter_counts_the_run_while_the_crop_is_pending(tmp_path, monkeypatch):
    monkeypatch.setenv(LEVEL_ENV, '1')
    monkeypatch.setenv(STORE_ENV, str(tmp_path / 'store'))
    hook.on_step2_finished(fake_app(tmp_path)).join(30)
    assert SampleStore(str(tmp_path / 'store')).counters() == {'crop_pending': 1}


def test_babelbrain_calls_the_hook_when_step2_finishes():
    """The one line in BabelBrain.py: the ultrasound branch of UpdateComputationalTime."""
    tree = ast.parse((BABELBRAIN_DIR / 'BabelBrain.py').read_text())
    method = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == 'UpdateComputationalTime')
    branch = next(n for n in ast.walk(method) if isinstance(n, ast.If)
                  and isinstance(n.test, ast.Compare)
                  and any(isinstance(c, ast.Constant) and c.value == 'ultrasound'
                          for c in n.test.comparators))
    calls = [n.func.id for n in ast.walk(ast.Module(body=branch.body, type_ignores=[]))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert 'on_step2_finished' in calls
