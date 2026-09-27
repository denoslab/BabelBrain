"""
The Step 2 hook: after a successful acoustic simulation, export a sample when FL is on.

BabelBrain calls ``on_step2_finished(self)`` from UpdateComputationalTime,
on the Step 2 worker's thread. The hook reads plain values only, never Qt
widgets, and does the export on a daemon thread. With FL off it returns at
once and imports nothing beyond the standard library. It never raises.
"""

import logging
import os
import threading

from . import FL_LEVELS, FL_OFF, LEVEL_ENV, STORE_ENV

logger = logging.getLogger(__name__)


def fl_level(config):
    """The FL level: the environment variable if set, else the saved setting, else off."""
    value = os.getenv(LEVEL_ENV)
    if value is None or value == '':
        value = (config or {}).get('FLLevel', FL_OFF)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return FL_OFF
    return value if value in FL_LEVELS else FL_OFF


def store_root(config):
    """The sample store folder: the environment variable, else the saved setting, else the default."""
    return os.getenv(STORE_ENV) or (config or {}).get('FLStore') or None


def snapshot(app):
    """Everything the exporter needs, as plain values, taken on the caller's thread."""
    config = app.Config
    return {
        'full_sol_path': app.AcSim._FullSolName,
        'water_sol_path': app.AcSim._WaterSolName,
        'store_root': store_root(config),
        'run_info': {
            'babelbrain_version': str(config.get('version', '')).strip(),
            'tx_system': config.get('TxSystem'),
            'frequency_hz': getattr(app, '_Frequency', None),
            'ppw': getattr(app, '_BasePPW', None),
            'bUseCT': config.get('bUseCT'),
            'CTType': config.get('CTType'),
            'options': dict(app.CommomAcOptions()),
            # Used only to derive the salted group id; never stored
            'subject_folder': os.path.dirname(str(config.get('T1W', ''))),
        },
    }


def _export(job):
    try:
        from .exporter import export_from_step2
        result = export_from_step2(job['full_sol_path'], job['water_sol_path'], job['run_info'],
                                   store_root=job['store_root'], source='live')
        logger.info('FL sample export: %s, %s', result.status, result.reason)
    except Exception as e:
        logger.warning('FL sample export failed: %s', e.__class__.__name__)


def on_step2_finished(app):
    """Start a background export if FL is on; return the thread, or None."""
    try:
        if fl_level(getattr(app, 'Config', None)) == FL_OFF:
            return None
        job = snapshot(app)
        thread = threading.Thread(target=_export, args=(job,), name='FLSampleExport', daemon=True)
        thread.start()
        return thread
    except Exception as e:
        logger.warning('FL hook skipped: %s', e.__class__.__name__)
        return None
