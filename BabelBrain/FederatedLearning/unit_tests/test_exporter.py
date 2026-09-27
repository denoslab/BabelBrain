"""Tests for the FL sample exporter, store and eligibility rules, BB-01.

Run from BabelBrain/BabelBrain: python -m pytest FederatedLearning/tests
All inputs are synthetic.
"""

import importlib.util
import json
import os
import threading
from pathlib import Path

import h5py
import numpy as np
import pytest

from FederatedLearning import crop, eligibility, schema, synthetic
from FederatedLearning.exporter import export_from_step2, validate_arrays
from FederatedLearning.store import SampleStore

SUBJECT = 'Subject_Anonymous_42'


@pytest.fixture
def setup(tmp_path):
    subject = tmp_path / 'studies' / SUBJECT
    full, water = synthetic.fake_step2_outputs(str(subject))
    return {'store': str(tmp_path / 'store'), 'subject': str(subject), 'full': full, 'water': water}


def export(setup, crop_fn=None, **overrides):
    return export_from_step2(setup['full'], setup['water'],
                             synthetic.run_info(setup['subject'], **overrides),
                             store_root=setup['store'], crop=crop_fn or synthetic.fake_crop())


def manifest_lines(store_root):
    path = os.path.join(store_root, 'v1', 'manifest.jsonl')
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# --------------------------------------------------
# Export
# --------------------------------------------------

def test_exported_sample_follows_the_contract(setup):
    result = export(setup)
    assert result.status == 'exported', result
    (entry,) = manifest_lines(setup['store'])
    assert entry['sample_id'] == result.sample_id
    assert entry['file'] == '250000/{}.h5'.format(result.sample_id)
    assert entry['bucket_hz'] == 250000 and entry['ct_type'] == 'CT' and entry['source'] == 'live'
    assert len(entry['group_id']) == 64 and entry['split'] in ('train', 'val')
    path = os.path.join(setup['store'], 'v1', entry['file'])
    with h5py.File(path, 'r') as f:
        assert f.attrs['schema_version'] == '1.0'
        for name, (dtype, rank) in schema.SAMPLE_DATASETS.items():
            assert f[name].dtype == np.dtype(dtype) and f[name].ndim == rank
        assert f['skull_field'].shape == (2, 16, 16, 32)


def test_manifest_line_validates_against_the_schema(setup):
    jsonschema = pytest.importorskip('jsonschema')
    export(setup)
    with open(schema.SCHEMA_PATH) as f:
        validator = jsonschema.Draft202012Validator(json.load(f),
                                                    format_checker=jsonschema.FormatChecker())
    for line in manifest_lines(setup['store']):
        validator.validate(line)


def test_nothing_about_the_subject_is_stored(setup):
    export(setup)
    needles = [SUBJECT, os.path.basename(setup['full']), 'DataForSim', 'studies',
               os.path.dirname(setup['subject'])]
    for path in Path(setup['store']).rglob('*'):
        if path.is_file() and path.name != '.salt':
            data = path.read_bytes()
            for needle in needles:
                assert needle.encode() not in data, (needle, path.name)


def test_exporting_the_same_run_twice_gives_one_sample(setup):
    assert export(setup).status == 'exported'
    second = export(setup)
    assert (second.status, second.reason) == ('skipped', 'duplicate')
    assert len(manifest_lines(setup['store'])) == 1


def test_the_real_crop_is_pending_so_nothing_is_written(setup):
    assert not crop.CROP_IMPLEMENTED
    result = export_from_step2(setup['full'], setup['water'], synthetic.run_info(setup['subject']),
                               store_root=setup['store'])
    assert (result.status, result.reason) == ('rejected', 'crop_pending')
    assert not os.path.exists(os.path.join(setup['store'], 'v1', 'manifest.jsonl'))
    assert SampleStore(setup['store']).counters() == {'crop_pending': 1}


def test_a_crop_that_does_not_fit_is_counted(setup):
    def too_big(*args):
        raise crop.CropDoesNotFit()
    result = export(setup, crop_fn=too_big)
    assert result.reason == 'crop_outside_domain'


def test_errors_never_raise_and_never_mention_paths(setup, caplog):
    def broken(full, water, bucket):
        raise RuntimeError('failed at ' + full)
    result = export(setup, crop_fn=broken)
    assert (result.status, result.reason) == ('error', 'internal_error')
    assert SUBJECT not in caplog.text
    assert SampleStore(setup['store']).counters()['internal_error'] == 1


def test_bad_arrays_from_the_crop_are_refused(setup):
    def wrong(*args):
        arrays = synthetic.sample_arrays()
        arrays['skull_field'] = arrays['skull_field'][:, :8]
        return arrays
    assert export(setup, crop_fn=wrong).status == 'error'
    assert not os.path.exists(os.path.join(setup['store'], 'v1', '250000'))


def test_ineligible_runs_are_counted_by_reason(setup):
    assert export(setup, CTType=2).reason == 'not_real_ct'
    assert export(setup, frequency_hz=400e3).reason == 'frequency_out_of_bucket'
    assert export(setup, tx_system='CTX_500').reason == 'transducer_not_allowed'
    counters = SampleStore(setup['store']).counters()
    assert counters == {'not_real_ct': 1, 'frequency_out_of_bucket': 1, 'transducer_not_allowed': 1}


def test_starfish_reads_what_babelbrain_writes(setup, tmp_path):
    """The Starfish store reader, when a starfish-fl checkout sits next to BabelBrain."""
    pytest.importorskip('jsonschema')
    reader = None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / 'starfish-fl' / 'controller' / 'starfish' / 'controller' / 'tasks' \
            / 'babel_brain_fno' / 'store.py'
        if candidate.is_file():
            reader = candidate
            break
    if reader is None:
        pytest.skip('no starfish-fl checkout next to this repo')
    spec = importlib.util.spec_from_file_location('starfish_store', reader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for seed in range(3):
        full, water = synthetic.fake_step2_outputs(setup['subject'] + str(seed), seed=seed + 1)
        export_from_step2(full, water, synthetic.run_info(setup['subject'] + str(seed)),
                          store_root=setup['store'], crop=synthetic.fake_crop())
    samples = module.SampleStore(setup['store']).samples(250000)
    assert len(samples) == 3


# --------------------------------------------------
# Store
# --------------------------------------------------

def test_salt_and_group_id(tmp_path):
    store = SampleStore(str(tmp_path / 's'))
    assert len(store.salt()) == 32 and store.salt() == store.salt()
    a = store.group_id('/data/subject-a')
    assert a == store.group_id('/data/subject-a')
    assert a != store.group_id('/data/subject-b')
    other = SampleStore(str(tmp_path / 't'))
    assert other.group_id('/data/subject-a') != a


def test_split_is_by_subject_and_about_ten_percent(tmp_path):
    store = SampleStore(str(tmp_path / 's'))
    splits = [store.split_for_group(store.group_id('/s/{}'.format(i))) for i in range(2000)]
    share = splits.count('val') / len(splits)
    assert 0.07 < share < 0.13


def test_delete_removes_the_file_and_writes_a_tombstone(setup):
    result = export(setup)
    store = SampleStore(setup['store'])
    store.delete(result.sample_id)
    assert store.entries() == []
    assert manifest_lines(setup['store'])[-1] == {'sample_id': result.sample_id, 'deleted': True}
    assert not list(Path(setup['store'], 'v1', '250000').glob('*.h5'))


def test_concurrent_appends_keep_every_line(tmp_path):
    store = SampleStore(str(tmp_path / 's'))

    def worker(k):
        for i in range(20):
            store.append({'sample_id': '{}-{}'.format(k, i), 'n': i})

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(manifest_lines(str(tmp_path / 's'))) == 80


def test_no_temporary_files_are_left(setup):
    export(setup)
    leftovers = [p.name for p in Path(setup['store']).rglob('*') if p.name.startswith('.tmp-')]
    assert leftovers == []


# --------------------------------------------------
# Eligibility
# --------------------------------------------------

def test_each_rule_passes_and_fails(setup):
    info = synthetic.run_info(setup['subject'])
    for rule in eligibility.RUN_RULES:
        assert rule(info) == (True, 'ok'), rule.__name__
    failing = {
        eligibility.rule_ct: {'bUseCT': False},
        eligibility.rule_frequency: {'frequency_hz': 300e3},
        eligibility.rule_transducer: {'tx_system': 'H317'},
        eligibility.rule_version: {'babelbrain_version': '0.7.9'},
        eligibility.rule_options: {'options': dict(info['options'], bForceHomogenousMedium=True)},
    }
    for rule, overrides in failing.items():
        assert rule(dict(info, **overrides))[0] is False, rule.__name__
    assert eligibility.rule_step2_outputs(setup['full'], '/nope')[1] == 'missing_water_output'
    assert eligibility.rule_step2_outputs('/nope', setup['water'])[1] == 'missing_transcranial_output'


def test_frequency_tolerance_and_buckets():
    assert eligibility.bucket_for(250e3) == 250000
    assert eligibility.bucket_for(254e3) == 250000
    assert eligibility.bucket_for(256e3) is None
    assert eligibility.bucket_for(735e3) == 750000


def test_optimised_weights_are_not_default(setup):
    info = synthetic.run_info(setup['subject'])
    info['options']['OptimizedWeightsFile'] = 'weights.csv'
    assert eligibility.rule_options(info) == (False, 'nondefault_option')


def test_training_settings_confirmed_on_2026_09_27():
    """The model's training settings, answers T4 and T6. Change them only with the spec."""
    assert eligibility.FREQUENCY_TOLERANCE == 0.02
    assert eligibility.TX_ALLOWLIST == ('Single',)
    assert eligibility.REQUIRED_OPTIONS == {'bForceHomogenousMedium': False,
                                            'bExtractAirRegions': True,
                                            'bUseRayleighForWater': True}
    assert eligibility.REQUIRED_CT_MAP == ('GE', '120', 'B', '', '0.5, 0.6')
    assert crop.CROP_IMPLEMENTED is False


def test_ct_mapping_must_be_the_default(setup):
    info = synthetic.run_info(setup['subject'])
    # Saved settings come back from YAML as a list
    info['options']['CTMapCombo'] = list(eligibility.REQUIRED_CT_MAP)
    assert eligibility.rule_options(info) == (True, 'ok')
    info['options']['CTMapCombo'] = ('Siemens', '120', 'H', '', '0.5')
    assert eligibility.rule_options(info) == (False, 'nondefault_option')
    del info['options']['CTMapCombo']
    assert eligibility.rule_options(info) == (False, 'nondefault_option')


def test_vendored_schema_matches_the_docs():
    for parent in Path(__file__).resolve().parents:
        docs = parent / 'babelbrain-docs' / 'specs' / 'manifest.schema.json'
        if docs.is_file():
            with open(docs) as a, open(schema.SCHEMA_PATH) as b:
                assert json.load(a) == json.load(b)
            return
    pytest.skip('no babelbrain-docs checkout next to this repo')


def test_validate_arrays_accepts_the_synthetic_sample():
    arrays = validate_arrays(synthetic.sample_arrays())
    assert arrays['brain_mask'].dtype == np.uint8
