"""
Sample contract v1, the only interface with the Starfish BabelBrainFno task.

Mirrors babelbrain-docs/specs/00-sample-contract.md and manifest.schema.json.
Change it only with a schema_version bump and matching changes in Starfish.
"""

import os

SCHEMA_VERSION = '1.0'
# Schema 1.1, decision D6: the NeuroFUS test set carries a coarse target region class.
# Only the backfill tool with --eval-regions writes it; live exports stay at 1.0.
EVAL_SCHEMA_VERSION = '1.1'
REGIONS = ('P7', 'P8', 'PO7', 'TP7', 'TP8', 'other')
STORE_VERSION_DIR = 'v1'
MANIFEST_NAME = 'manifest.jsonl'
SALT_NAME = '.salt'
COUNTERS_NAME = '.counters.json'
DEFAULT_STORE = os.path.join(os.path.expanduser('~'), 'BabelBrainFL', 'samples')

# Frequency bucket in Hz -> voxel spacing in mm
BUCKET_SPACING_MM = {250000: 0.490, 500000: 0.368, 750000: 0.245}
BUCKETS_HZ = tuple(sorted(BUCKET_SPACING_MM))
CROP_MM = (41.2, 41.2, 82.4)

# Datasets in a sample file: name -> (dtype, rank)
SAMPLE_DATASETS = {
    'ct_hu': ('float32', 3),
    'water_field': ('float32', 4),
    'skull_field': ('float32', 4),
    'sos': ('float32', 3),
    'attenuation': ('float32', 3),
    'brain_mask': ('uint8', 3),
}
COMPLEX_FIELDS = ('water_field', 'skull_field')

# Manifest line fields
REQUIRED_FIELDS = ('sample_id', 'schema_version', 'file', 'sha256', 'frequency_hz', 'bucket_hz',
                   'spacing_mm', 'babelbrain_version', 'tx_system', 'ct_type', 'group_id',
                   'split', 'source')
OPTIONAL_FIELDS = ('ppw', 'focal_length_mm', 'aperture_mm', 'exported_month', 'fingerprint',
                   'region')
SOURCES = ('live', 'backfill')
SPLITS = ('train', 'val')

# Share of subjects, not samples, that go to the local val split
VAL_PERCENT = 10

# Never written to a sample or the manifest, documented here to keep it in view:
# names, dates other than exported_month, file names or paths, NIfTI headers,
# scanner affines, subject IDs, target names, trajectory files, T1w or T2w MRI.
# The one exception is the region class above, in the NeuroFUS test set only.
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manifest.schema.json')
