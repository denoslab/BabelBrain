"""
Synthetic samples for tests: tiny, random, valid under sample contract v1.

Nothing here comes from a real subject. The layout matches the Starfish
generator, controller/starfish/controller/tasks/babel_brain_fno/synthetic.py.
"""

import os

import numpy as np

from . import schema

DEFAULT_SHAPE = (16, 16, 32)


def sample_arrays(shape=DEFAULT_SHAPE, seed=0):
    """Random arrays named, typed and shaped as in schema.SAMPLE_DATASETS."""
    rng = np.random.default_rng(seed)
    x, y, z = shape
    return {
        'ct_hu': rng.uniform(-1000, 2000, shape).astype(np.float32),
        'water_field': rng.standard_normal((2, x, y, z)).astype(np.float32),
        'skull_field': rng.standard_normal((2, x, y, z)).astype(np.float32),
        'sos': rng.uniform(1400, 3000, shape).astype(np.float32),
        'attenuation': rng.uniform(0, 100, shape).astype(np.float32),
        'brain_mask': (rng.random(shape) > 0.5).astype(np.uint8),
    }


def fake_crop(shape=DEFAULT_SHAPE):
    """A stand-in for crop.crop_sample that returns random arrays, for tests only."""
    def crop(full_sol_path, water_sol_path, bucket_hz):
        with open(full_sol_path, 'rb') as f:
            seed = int.from_bytes(f.read(4).ljust(4, b'\0'), 'little')
        return sample_arrays(shape, seed)
    return crop


def fake_step2_outputs(folder, prefix='Subject_Single_250kHz_9PPW_', seed=0):
    """Two small files standing in for DataForSim.h5 and Water_DataForSim.h5."""
    os.makedirs(folder, exist_ok=True)
    full = os.path.join(folder, prefix + 'DataForSim.h5')
    water = os.path.join(folder, prefix + 'Water_DataForSim.h5')
    rng = np.random.default_rng(seed)
    for path in (full, water):
        with open(path, 'wb') as f:
            f.write(rng.bytes(1024))
    return full, water


def run_info(subject_folder, **overrides):
    """A run_info snapshot that passes every eligibility rule."""
    info = {
        'babelbrain_version': '0.8.2',
        'tx_system': 'Single',
        'frequency_hz': 250e3,
        'ppw': 9,
        'bUseCT': True,
        'CTType': 1,
        'focal_length_mm': 50.0,
        'aperture_mm': 50.0,
        'options': {'bForceHomogenousMedium': False, 'bExtractAirRegions': True,
                    'bUseRayleighForWater': True, 'OptimizedWeightsFile': '',
                    'CTMapCombo': (0, 0)},
        'subject_folder': subject_folder,
    }
    info.update(overrides)
    return info


def spacing(bucket_hz):
    return schema.BUCKET_SPACING_MM[bucket_hz]
