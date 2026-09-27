"""
The local sample store, laid out as in sample contract v1.

    <store_root>/v1/manifest.jsonl          one JSON line per sample, append-only
    <store_root>/v1/<bucket_hz>/<id>.h5     one file per sample
    <store_root>/v1/.salt                   32 random bytes, never leaves the machine

Sample files are written once, to a temporary name and then renamed, and
never changed afterwards. Deleting a sample removes its file and appends a
tombstone line. The manifest is appended under a lock file, so a live export
and a backfill can run at the same time.
"""

import hashlib
import hmac
import json
import os
import tempfile
import time
import uuid

from . import schema

LOCK_TIMEOUT_S = 30
STALE_LOCK_S = 120


class StoreError(Exception):
    pass


def sha256_file(path, chunk_size=1 << 20):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(chunk_size), b''):
            digest.update(block)
    return digest.hexdigest()


class SampleStore:

    def __init__(self, root=None):
        self.root = os.path.abspath(os.path.expanduser(root or schema.DEFAULT_STORE))
        self.version_root = os.path.join(self.root, schema.STORE_VERSION_DIR)
        self.manifest_path = os.path.join(self.version_root, schema.MANIFEST_NAME)
        self.lock_path = self.manifest_path + '.lock'
        self.counters_path = os.path.join(self.version_root, schema.COUNTERS_NAME)

    # --------------------------------------------------
    # Subject grouping, never reversible without the local salt
    # --------------------------------------------------

    def salt(self):
        path = os.path.join(self.version_root, schema.SALT_NAME)
        os.makedirs(self.version_root, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(os.urandom(32))
        except FileExistsError:
            pass
        with open(path, 'rb') as f:
            value = f.read()
        if len(value) != 32:
            raise StoreError('the store salt is damaged')
        return value

    def group_id(self, subject_folder):
        """HMAC-SHA256 of the subject's input folder with the local salt."""
        key = os.path.normcase(os.path.abspath(str(subject_folder))).encode()
        return hmac.new(self.salt(), key, hashlib.sha256).hexdigest()

    @staticmethod
    def split_for_group(group_id):
        """train or val, by subject: every target of one subject lands in the same split."""
        return 'val' if int(group_id[:8], 16) % 100 < schema.VAL_PERCENT else 'train'

    # --------------------------------------------------
    # Manifest
    # --------------------------------------------------

    def _lock(self):
        os.makedirs(self.version_root, exist_ok=True)
        deadline = time.time() + LOCK_TIMEOUT_S
        while True:
            try:
                return os.open(self.lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.lock_path) > STALE_LOCK_S:
                        os.remove(self.lock_path)
                        continue
                except OSError:
                    continue
                if time.time() > deadline:
                    raise StoreError('the store manifest is locked')
                time.sleep(0.05)

    def _unlock(self, fd):
        os.close(fd)
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

    def append(self, entry):
        """Append one manifest line under the lock."""
        line = json.dumps(entry, sort_keys=True) + '\n'
        fd = self._lock()
        try:
            with open(self.manifest_path, 'a') as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        finally:
            self._unlock(fd)

    def entries(self):
        """Live manifest entries, in order, with deleted samples left out."""
        if not os.path.isfile(self.manifest_path):
            return []
        live, deleted = {}, set()
        with open(self.manifest_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get('deleted'):
                    deleted.add(entry.get('sample_id'))
                elif 'sample_id' in entry:
                    live.setdefault(entry['sample_id'], entry)
        return [e for sid, e in live.items() if sid not in deleted]

    def fingerprints(self):
        return {e.get('fingerprint') for e in self.entries() if e.get('fingerprint')}

    # --------------------------------------------------
    # Samples
    # --------------------------------------------------

    @staticmethod
    def new_sample_id():
        return str(uuid.uuid4())

    def sample_path(self, bucket_hz, sample_id):
        return os.path.join(self.version_root, str(int(bucket_hz)), sample_id + '.h5')

    def write_sample_file(self, bucket_hz, sample_id, write):
        """Call ``write(tmp_path)`` to create the file, then move it into place; return its SHA-256."""
        final = self.sample_path(bucket_hz, sample_id)
        folder = os.path.dirname(final)
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix='.tmp-', suffix='.h5')
        os.close(fd)
        try:
            write(tmp)
            digest = sha256_file(tmp)
            os.replace(tmp, final)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        return digest

    def delete(self, sample_id):
        """Remove a sample: delete its file and append a tombstone."""
        for entry in self.entries():
            if entry['sample_id'] == sample_id:
                path = os.path.join(self.version_root, entry['file'])
                if os.path.exists(path):
                    os.remove(path)
                break
        self.append({'sample_id': sample_id, 'deleted': True})

    # --------------------------------------------------
    # Counters for the FL tab: exports and rejections by reason, no paths
    # --------------------------------------------------

    def count(self, outcome):
        fd = self._lock()
        try:
            counters = self.counters()
            counters[outcome] = counters.get(outcome, 0) + 1
            tmp = self.counters_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(counters, f, sort_keys=True)
            os.replace(tmp, self.counters_path)
        finally:
            self._unlock(fd)

    def counters(self):
        try:
            with open(self.counters_path) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def summary(self):
        """Sample counts per bucket and split, and disk use in bytes."""
        per_bucket, used = {}, 0
        for e in self.entries():
            key = (e.get('bucket_hz'), e.get('split'))
            per_bucket[key] = per_bucket.get(key, 0) + 1
            try:
                used += os.path.getsize(os.path.join(self.version_root, e['file']))
            except OSError:
                pass
        return {'counts': per_bucket, 'bytes': used, 'outcomes': self.counters()}
