"""
Eligibility rules v1: which Step 2 runs may become training samples.

Each rule returns ``(ok, reason)``. Reasons are short codes, counted for the
FL tab and never logged with paths. Values marked CONFIRM wait for Tayeb's
answers, questions T4 to T6 in babelbrain-docs/open-questions.md; a test pins
each one, so changing it is a deliberate edit.
"""

import os

from . import schema

# CTType index in the BabelBrain input dialog: 0 no CT, 1 real CT, 2 ZTE, 3 PETRA, 4 density
CT_TYPE_REAL_CT = 1

# CONFIRM with Tayeb, T6: how far the run's frequency may be from its bucket
FREQUENCY_TOLERANCE = 0.02
# CONFIRM with Tayeb, T6: transducers whose fields the model was trained on
TX_ALLOWLIST = ('Single',)
BABELBRAIN_VERSION_ALLOWLIST = ('0.8.1', '0.8.2')
# CONFIRM with Tayeb, T4: the physics options of the training simulations, as in
# CommomAcOptions(). These are BabelBrain's defaults.
REQUIRED_OPTIONS = {
    'bForceHomogenousMedium': False,
    'bExtractAirRegions': True,
    'bUseRayleighForWater': True,
}
# CONFIRM with Tayeb, T4: the CT mapping, CTMapCombo, his simulations used. None skips the check.
REQUIRED_CT_MAP = None


def rule_step2_outputs(full_sol_path, water_sol_path):
    """Rule 1: both Step 2 outputs exist."""
    if not (full_sol_path and os.path.isfile(full_sol_path)):
        return False, 'missing_transcranial_output'
    if not (water_sol_path and os.path.isfile(water_sol_path)):
        return False, 'missing_water_output'
    return True, 'ok'


def rule_ct(run_info):
    """Rule 2: planned with a real CT."""
    if not run_info.get('bUseCT') or run_info.get('CTType') != CT_TYPE_REAL_CT:
        return False, 'not_real_ct'
    return True, 'ok'


def bucket_for(frequency_hz):
    """The frequency bucket within tolerance, or None."""
    for bucket in schema.BUCKETS_HZ:
        if abs(float(frequency_hz) - bucket) <= FREQUENCY_TOLERANCE * bucket:
            return bucket
    return None


def rule_frequency(run_info):
    """Rule 3: frequency near 250, 500 or 750 kHz."""
    try:
        bucket = bucket_for(run_info.get('frequency_hz'))
    except (TypeError, ValueError):
        return False, 'no_frequency'
    return (True, 'ok') if bucket else (False, 'frequency_out_of_bucket')


def rule_transducer(run_info):
    """Rule 4: a transducer on the allowlist."""
    return (True, 'ok') if run_info.get('tx_system') in TX_ALLOWLIST else (False, 'transducer_not_allowed')


def rule_version(run_info):
    """Rule 5: a BabelBrain version on the allowlist."""
    version = str(run_info.get('babelbrain_version', '')).strip()
    return (True, 'ok') if version in BABELBRAIN_VERSION_ALLOWLIST else (False, 'version_not_allowed')


def rule_options(run_info):
    """Rule 6: default physics options, and no optimised weights file."""
    options = run_info.get('options') or {}
    for name, value in REQUIRED_OPTIONS.items():
        if options.get(name) != value:
            return False, 'nondefault_option'
    if options.get('OptimizedWeightsFile'):
        return False, 'nondefault_option'
    if REQUIRED_CT_MAP is not None and options.get('CTMapCombo') != REQUIRED_CT_MAP:
        return False, 'nondefault_option'
    return True, 'ok'


RUN_RULES = (rule_ct, rule_frequency, rule_transducer, rule_version, rule_options)


def check(full_sol_path, water_sol_path, run_info):
    """Rules 1 to 6 in order; the first failure wins. Rule 7, the crop fit, is in crop.py."""
    ok, reason = rule_step2_outputs(full_sol_path, water_sol_path)
    if not ok:
        return ok, reason
    for rule in RUN_RULES:
        ok, reason = rule(run_info)
        if not ok:
            return ok, reason
    return True, 'ok'
