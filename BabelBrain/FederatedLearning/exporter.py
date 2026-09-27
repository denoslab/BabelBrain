"""
Turn one finished Step 2 run into one training sample in the local store.

``export_from_step2`` never raises: every outcome, including an internal
error, is returned as an ExportResult and counted by reason in the store, so
a problem here can never fail a simulation. Nothing about the subject is
written: no names, paths, headers, affines, dates other than the month, or
target names.
"""

import collections
import datetime
import logging

import numpy as np

from . import crop as crop_module
from . import eligibility, schema
from .store import SampleStore, sha256_file

logger = logging.getLogger(__name__)

ExportResult = collections.namedtuple('ExportResult', 'status reason sample_id')


class SampleArrayError(Exception):
    pass


def validate_arrays(arrays):
    """Every contract dataset, with its dtype and rank, on one grid."""
    missing = [n for n in schema.SAMPLE_DATASETS if n not in arrays]
    if missing:
        raise SampleArrayError('missing ' + ', '.join(missing))
    grid = np.asarray(arrays['ct_hu']).shape
    out = {}
    for name, (dtype, rank) in schema.SAMPLE_DATASETS.items():
        arr = np.ascontiguousarray(arrays[name], dtype=dtype)
        expected = (2,) + grid if name in schema.COMPLEX_FIELDS else grid
        if arr.ndim != rank or arr.shape != expected:
            raise SampleArrayError('{} has shape {}, expected {}'.format(name, arr.shape, expected))
        if arr.dtype.kind == 'f' and not np.all(np.isfinite(arr)):
            raise SampleArrayError('{} has non-finite values'.format(name))
        out[name] = arr
    return out


def _write_h5(path, arrays, sample_id, frequency_hz, bucket_hz):
    import h5py
    with h5py.File(path, 'w') as f:
        for name, arr in arrays.items():
            f.create_dataset(name, data=arr)
        f.attrs['schema_version'] = schema.SCHEMA_VERSION
        f.attrs['sample_id'] = sample_id
        f.attrs['frequency_hz'] = float(frequency_hz)
        f.attrs['spacing_mm'] = schema.BUCKET_SPACING_MM[bucket_hz]
        f.attrs['crop_mm'] = np.array(schema.CROP_MM)


def _optional_float(value):
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def export_from_step2(full_sol_path, water_sol_path, run_info, store_root=None, source='live',
                      crop=None, today=None):
    """
    Export one run. ``run_info`` is a plain dict snapshot taken on the caller's thread:

    babelbrain_version, tx_system, frequency_hz, ppw, bUseCT, CTType,
    focal_length_mm, aperture_mm, options (as from CommomAcOptions) and
    subject_folder, which is used only to derive the salted group_id.
    """
    crop = crop or crop_module.crop_sample
    store = None
    try:
        store = SampleStore(store_root)
        ok, reason = eligibility.check(full_sol_path, water_sol_path, run_info)
        if not ok:
            store.count(reason)
            return ExportResult('rejected', reason, None)

        fingerprint = sha256_file(full_sol_path)
        if fingerprint in store.fingerprints():
            store.count('duplicate')
            return ExportResult('skipped', 'duplicate', None)

        frequency = float(run_info['frequency_hz'])
        bucket = eligibility.bucket_for(frequency)
        try:
            arrays = validate_arrays(crop(full_sol_path, water_sol_path, bucket))
        except crop_module.CropNotAvailable:
            store.count('crop_pending')
            return ExportResult('rejected', 'crop_pending', None)
        except crop_module.CropDoesNotFit:
            store.count('crop_outside_domain')
            return ExportResult('rejected', 'crop_outside_domain', None)

        sample_id = store.new_sample_id()
        digest = store.write_sample_file(
            bucket, sample_id, lambda tmp: _write_h5(tmp, arrays, sample_id, frequency, bucket))
        group_id = store.group_id(run_info['subject_folder'])
        today = today or datetime.date.today()
        entry = {
            'sample_id': sample_id,
            'schema_version': schema.SCHEMA_VERSION,
            'file': '{}/{}.h5'.format(bucket, sample_id),
            'sha256': digest,
            'frequency_hz': frequency,
            'bucket_hz': bucket,
            'spacing_mm': schema.BUCKET_SPACING_MM[bucket],
            'babelbrain_version': str(run_info['babelbrain_version']).strip(),
            'tx_system': run_info['tx_system'],
            'ct_type': 'CT',
            'group_id': group_id,
            'split': store.split_for_group(group_id),
            'exported_month': today.strftime('%Y-%m'),
            'source': source,
            'fingerprint': fingerprint,
        }
        for key, value in (('ppw', run_info.get('ppw')),
                           ('focal_length_mm', run_info.get('focal_length_mm')),
                           ('aperture_mm', run_info.get('aperture_mm'))):
            value = _optional_float(value)
            if value is not None:
                entry[key] = value
        store.append(entry)
        store.count('exported')
        return ExportResult('exported', 'ok', sample_id)
    except Exception as e:
        # The reason code only: exception text could carry a path
        logger.warning('FL sample export failed: %s', e.__class__.__name__)
        try:
            if store is not None:
                store.count('internal_error')
        except Exception:
            pass
        return ExportResult('error', 'internal_error', None)
