"""
Seed a lab's sample store from Step 2 runs it has already done, BB-03.

    python -m FederatedLearning.backfill <folder> [--store PATH] [--dry-run]
        [--babelbrain-version 0.8.1] [--real-ct] [--default-options]

Run from BabelBrain/BabelBrain. It walks <folder> for *DataForSim.h5 files
with a matching Water_ file and exports each eligible run with source
"backfill". Frequency, PPW and transducer come from the output file name.
What BabelBrain does not save with a run, the BabelBrain version, the CT
type and the physics options, must be stated by the operator for the whole
folder; a run without them is skipped as missing_info. --dry-run prints
counts per frequency and per reason and writes nothing. Output never shows
paths or file names, which can hold subject and target names.
"""

import argparse
import collections
import os
import re
import sys

from . import eligibility
from .store import SampleStore, sha256_file

SUFFIX = 'DataForSim.h5'
WATER_SUFFIX = 'Water_DataForSim.h5'
# Every transducer BabelBrain offers, for reading the file name; eligibility decides which count
KNOWN_TX = ('Single', 'CTX_500', 'CTX_250', 'CTX_250_2ch', 'DPX_500', 'DPXPC_300', 'H317', 'H246',
            'BSonix', 'REMOPD', 'I12378', 'ATAC', 'R15148', 'R15287', 'R15473', 'R15646',
            'IGT64_500', 'H301', 'DomeTx')
_NAME = re.compile(r'_(?P<khz>\d+)kHz_(?P<ppw>\d+)PPW_')


def find_runs(folder):
    """(full, water) pairs under folder, in a stable order."""
    runs = []
    for root, _, files in os.walk(folder):
        for name in files:
            if name.endswith(SUFFIX) and not name.endswith(WATER_SUFFIX):
                water = name[:-len(SUFFIX)] + WATER_SUFFIX
                if water in files:
                    runs.append((os.path.join(root, name), os.path.join(root, water)))
    return sorted(runs)


def parse_name(name):
    """Transducer, frequency in Hz and PPW from <ID>_<Tx>_<kHz>kHz_<PPW>PPW_...DataForSim.h5."""
    match = _NAME.search(name)
    if not match:
        return None
    head = name[:match.start()]
    tx = next((t for t in sorted(KNOWN_TX, key=len, reverse=True) if head.endswith('_' + t)), None)
    return {'tx_system': tx, 'frequency_hz': float(match.group('khz')) * 1e3,
            'ppw': int(match.group('ppw'))}


def _scalar(f, key):
    try:
        value = f[key][()]
        return float(value) if getattr(value, 'size', 1) == 1 else None
    except (KeyError, TypeError, ValueError):
        return None


def recover_run_info(full, args):
    """run_info for one past run, or None when a required value cannot be recovered."""
    parsed = parse_name(os.path.basename(full))
    if not parsed or not parsed['tx_system']:
        return None
    if not (args.babelbrain_version and args.real_ct and args.default_options):
        return None
    info = dict(parsed)
    info.update({
        'babelbrain_version': args.babelbrain_version,
        'bUseCT': True, 'CTType': eligibility.CT_TYPE_REAL_CT,
        'options': dict(eligibility.REQUIRED_OPTIONS, OptimizedWeightsFile=''),
        # Default BabelBrain output folder is the T1W folder, as for live exports
        'subject_folder': os.path.dirname(full),
    })
    try:
        import h5py
        with h5py.File(full, 'r') as f:
            focal, aperture = _scalar(f, 'FocalLength'), _scalar(f, 'Aperture')
        # CONFIRM on the ernie run, Phase 0: DataForSim is assumed to store metres
        info['focal_length_mm'] = focal * 1e3 if focal is not None else None
        info['aperture_mm'] = aperture * 1e3 if aperture is not None else None
    except Exception:
        pass
    return info


def run(folder, store_root=None, dry_run=False, args=None, crop=None, out=None):
    """Back-fill a folder; returns a Counter of outcomes. Prints only counts."""
    from .exporter import export_from_step2
    out = out or sys.stdout
    store = SampleStore(store_root)
    known = store.fingerprints()
    outcomes, buckets = collections.Counter(), collections.Counter()
    for full, water in find_runs(folder):
        info = recover_run_info(full, args)
        if info is None:
            outcomes['missing_info'] += 1
            if not dry_run:
                store.count('missing_info')
            continue
        if dry_run:
            ok, reason = eligibility.check(full, water, info)
            if ok and sha256_file(full) in known:
                ok, reason = False, 'duplicate'
            outcomes['eligible' if ok else reason] += 1
            if ok:
                buckets[eligibility.bucket_for(info['frequency_hz'])] += 1
            continue
        result = export_from_step2(full, water, info, store_root=store_root, source='backfill',
                                   crop=crop)
        outcomes[result.reason if result.status != 'exported' else 'exported'] += 1
        if result.status == 'exported':
            buckets[eligibility.bucket_for(info['frequency_hz'])] += 1
    verb = 'would export' if dry_run else 'exported'
    print('Runs found: {}'.format(sum(outcomes.values())), file=out)
    for bucket, n in sorted(buckets.items()):
        print('  {} at {} kHz: {}'.format(verb, bucket // 1000, n), file=out)
    for reason, n in sorted(outcomes.items()):
        print('  {}: {}'.format(reason.replace('_', ' '), n), file=out)
    return outcomes


def main(argv=None):
    parser = argparse.ArgumentParser(description='Back-fill the FL sample store from past Step 2 runs.')
    parser.add_argument('folder')
    parser.add_argument('--store', default=None, help='sample store folder, default ~/BabelBrainFL/samples')
    parser.add_argument('--dry-run', action='store_true', help='count only, write nothing')
    parser.add_argument('--babelbrain-version', default=None,
                        help='the BabelBrain version every run in the folder was made with')
    parser.add_argument('--real-ct', action='store_true',
                        help='state that every run in the folder was planned with a real CT')
    parser.add_argument('--default-options', action='store_true',
                        help='state that every run used the default physics options')
    args = parser.parse_args(argv)
    run(args.folder, store_root=args.store or os.getenv('BABELBRAIN_FL_STORE'),
        dry_run=args.dry_run, args=args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
