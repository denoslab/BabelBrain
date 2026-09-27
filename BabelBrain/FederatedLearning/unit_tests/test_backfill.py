"""Tests for the backfill tool, BB-03. Synthetic runs only."""

import io
import os
from types import SimpleNamespace

import h5py
import numpy as np

from FederatedLearning import backfill, synthetic
from FederatedLearning.store import SampleStore

STATED = SimpleNamespace(babelbrain_version='0.8.1', real_ct=True, default_options=True)
UNSTATED = SimpleNamespace(babelbrain_version=None, real_ct=False, default_options=False)


def make_run(folder, prefix, seed):
    os.makedirs(folder, exist_ok=True)
    full = os.path.join(folder, prefix + 'DataForSim.h5')
    water = os.path.join(folder, prefix + 'Water_DataForSim.h5')
    rng = np.random.default_rng(seed)
    with h5py.File(full, 'w') as f:
        f['FocalLength'] = 0.05
        f['Aperture'] = 0.05
        f['p_complex'] = rng.standard_normal(8)
    with h5py.File(water, 'w') as f:
        f['p_complex'] = rng.standard_normal(8)
    return full


def lab_folder(tmp_path):
    root = tmp_path / 'lab'
    make_run(str(root / 'SubjA'), 'SubjA_LeftVIM_12_Aug_2026_Single_250kHz_9PPW_Foc50.0_Diam50.0_', 1)
    make_run(str(root / 'SubjB'), 'SubjB_Target_Single_250kHz_6PPW_', 2)
    make_run(str(root / 'SubjC'), 'SubjC_Target_Single_400kHz_6PPW_', 3)
    make_run(str(root / 'SubjD'), 'SubjD_Target_CTX_250_2ch_250kHz_9PPW_', 4)
    # a transcranial file without its water file is not a run
    with h5py.File(str(root / 'SubjD' / 'Lonely_Single_250kHz_9PPW_DataForSim.h5'), 'w') as f:
        f['x'] = 1
    return str(root)


def test_parse_name():
    assert backfill.parse_name('S1_T_Single_250kHz_9PPW_DataForSim.h5') == {
        'tx_system': 'Single', 'frequency_hz': 250000.0, 'ppw': 9}
    assert backfill.parse_name('S1_T_CTX_250_2ch_500kHz_6PPW_x_DataForSim.h5')['tx_system'] == 'CTX_250_2ch'
    assert backfill.parse_name('S1_T_Unknown_250kHz_9PPW_DataForSim.h5')['tx_system'] is None
    assert backfill.parse_name('no_frequency_DataForSim.h5') is None


def test_dry_run_counts_and_writes_nothing(tmp_path):
    out = io.StringIO()
    store = str(tmp_path / 'store')
    outcomes = backfill.run(lab_folder(tmp_path), store_root=store, dry_run=True, args=STATED, out=out)
    assert outcomes == {'eligible': 2, 'frequency_out_of_bucket': 1, 'transducer_not_allowed': 1}
    assert 'would export at 250 kHz: 2' in out.getvalue()
    assert not os.path.exists(store)


def test_unstated_facts_mean_missing_info(tmp_path):
    outcomes = backfill.run(lab_folder(tmp_path), store_root=str(tmp_path / 'store'),
                            dry_run=True, args=UNSTATED, out=io.StringIO())
    assert outcomes == {'missing_info': 4}


def test_real_run_exports_only_eligible_runs_once(tmp_path):
    folder, store = lab_folder(tmp_path), str(tmp_path / 'store')
    outcomes = backfill.run(folder, store_root=store, args=STATED, crop=synthetic.fake_crop(),
                            out=io.StringIO())
    assert outcomes['exported'] == 2
    entries = SampleStore(store).entries()
    assert len(entries) == 2 and {e['source'] for e in entries} == {'backfill'}
    assert {e.get('focal_length_mm') for e in entries} == {50.0}
    again = backfill.run(folder, store_root=store, args=STATED, crop=synthetic.fake_crop(),
                         out=io.StringIO())
    assert again['duplicate'] == 2 and 'exported' not in again
    assert len(SampleStore(store).entries()) == 2


def test_real_crop_pending_exports_nothing(tmp_path):
    outcomes = backfill.run(lab_folder(tmp_path), store_root=str(tmp_path / 'store'), args=STATED,
                            out=io.StringIO())
    assert outcomes['crop_pending'] == 2


def test_output_never_shows_names(tmp_path):
    out = io.StringIO()
    backfill.run(lab_folder(tmp_path), store_root=str(tmp_path / 'store'), dry_run=True,
                 args=STATED, out=out)
    for needle in ('SubjA', 'LeftVIM', 'Aug_2026', 'DataForSim', str(tmp_path)):
        assert needle not in out.getvalue()


def test_command_line(tmp_path, capsys):
    folder = lab_folder(tmp_path)
    assert backfill.main([folder, '--store', str(tmp_path / 's'), '--dry-run',
                          '--babelbrain-version', '0.8.1', '--real-ct', '--default-options']) == 0
    assert 'Runs found: 4' in capsys.readouterr().out


# --------------------------------------------------
# Region labels for the NeuroFUS test set, D6
# --------------------------------------------------

EVAL = SimpleNamespace(babelbrain_version='0.8.1', real_ct=True, default_options=True,
                       eval_regions=True)


def test_region_from_name_takes_whole_tokens_of_the_target():
    tail = '_Single_250kHz_9PPW_DataForSim.h5'
    cases = {'S01_P7': 'P7', 'S01_PO7': 'PO7', 'S01_TP7': 'TP7', 'S01_tp8-2': 'TP8',
             'S01_Left_P8_12_Aug_2026': 'P8', 'S01_LeftVIM': 'other', 'S01_P71': 'other',
             'S01_P7_P8': 'other', 'S01_Target': 'other'}
    for target, region in cases.items():
        assert backfill.region_from_name(target + tail) == region, target
    # A transducer name is never read as a target
    assert backfill.region_from_name('S01_Target_CTX_250_2ch_250kHz_9PPW_DataForSim.h5') == 'other'
    assert backfill.region_from_name('no_frequency_DataForSim.h5') == 'other'


def eval_folder(tmp_path):
    root = tmp_path / 'test-subjects'
    make_run(str(root / 'S1'), 'S1_PO7_Single_250kHz_9PPW_', 11)
    make_run(str(root / 'S2'), 'S2_TP8_Single_250kHz_9PPW_', 12)
    make_run(str(root / 'S3'), 'S3_LeftVIM_Single_250kHz_9PPW_', 13)
    return str(root)


def test_eval_regions_dry_run_counts_per_region(tmp_path):
    out = io.StringIO()
    backfill.run(eval_folder(tmp_path), store_root=str(tmp_path / 'eval'), dry_run=True,
                 args=EVAL, out=out)
    text = out.getvalue()
    for line in ('would export in region PO7: 1', 'would export in region TP8: 1',
                 'would export in region other: 1', 'would export in region P7: 0'):
        assert line in text
    assert 'LeftVIM' not in text and 'S1' not in text


def test_eval_regions_export_writes_1_1_with_regions(tmp_path):
    store = str(tmp_path / 'eval')
    outcomes = backfill.run(eval_folder(tmp_path), store_root=store, args=EVAL,
                            crop=synthetic.fake_crop(), out=io.StringIO())
    assert outcomes['exported'] == 3
    entries = SampleStore(store).entries()
    assert sorted(e['region'] for e in entries) == ['PO7', 'TP8', 'other']
    assert {e['schema_version'] for e in entries} == {'1.1'}
    text = open(os.path.join(store, 'v1', 'manifest.jsonl')).read()
    assert 'LeftVIM' not in text and 'S3' not in text


def test_without_the_flag_backfill_writes_no_region(tmp_path):
    store = str(tmp_path / 'lab-store')
    backfill.run(eval_folder(tmp_path), store_root=store, args=STATED,
                 crop=synthetic.fake_crop(), out=io.StringIO())
    entries = SampleStore(store).entries()
    assert len(entries) == 3 and all('region' not in e for e in entries)
    assert {e['schema_version'] for e in entries} == {'1.0'}


def test_command_line_eval_regions(tmp_path, capsys):
    assert backfill.main([eval_folder(tmp_path), '--store', str(tmp_path / 's'), '--dry-run',
                          '--babelbrain-version', '0.8.1', '--real-ct', '--default-options',
                          '--eval-regions']) == 0
    assert 'would export in region PO7: 1' in capsys.readouterr().out
