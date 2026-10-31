"""A replaced worker must preserve its trusted frontier through interrupted commits."""
from pathlib import Path
import sys
import unittest
F = Path(__file__).resolve().parents[1] / 'frontend'
sys.path.insert(0, str(F))
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile, struct, hashlib
from pgn_engine import retire_replaced_worker, original_emission_floor
from pgn_native_contract import fields, magic, rebase_pin, reset_new_args
from pgn_session import SessionStore
from pgn_threshold_policy import verify_pin

class ResumeReplacementTests(unittest.TestCase):

    def test_contract(self):
        """A replaced worker must preserve its trusted frontier through interrupted commits."""
        prime = 190121201168499697841
        checks = []
        with tempfile.TemporaryDirectory(prefix='scout-worker-upgrade-') as temporary:
            root = Path(temporary)
            replacement = root / 'new-not-executable.bin'
            replacement.write_bytes(b'bound replacement fixture; never executed')
            for checkpoint in (False, True):
                for fault in ('none', 'journal_before_database', 'database_before_cache'):
                    folder = root / str(checkpoint) / fault
                    cfg = dict(start=str(prime), end=str(prime + 10000), bins=10, target_merit=32, report_top=100, **fields(prime, prime + 10000, 1000))
                    store = SessionStore.create(folder, cfg, {'uuid': 'binding-test'})
                    old = root / 'removed-old.bin'
                    old.write_bytes(b'old binding; must not execute')
                    chunk = store.bind_chunk(start=prime, length=10000, worker=old, worker_sha256=hashlib.sha256(old.read_bytes()).hexdigest().upper(), profile_k=8, base_positions=0, base_tests=0, gap_min=1000, threshold_policy_sha256=cfg['threshold_policy']['sha256'], worker_source_sha256='A' * 64)
                    if checkpoint:
                        store.record_gap(prime, prime + 1500, 'known independently verified fixture')
                        store.accepted_progress(1000, 7)
                        raw = struct.pack('<8s7Q', magic(1000), prime & (1 << 64) - 1, prime >> 64, 10000, 1000, 7, 0, 0)
                        cp = folder / 'native-checkpoint.bin'
                        cp.write_bytes(raw)
                        store.capture_closed_checkpoint(cp, 1000, 7)
                    store.closed('PAUSED', 0, 0)
                    store.accepted_progress(5000, 100)
                    old.unlink()
                    boundaries = []
                    original_apply = store.gaps.apply

                    def injected(event, offset):
                        if event['type'] == 'chunk_closed' and fault == 'journal_before_database':
                            raise OSError('injected after durable journal')
                        return original_apply(event, offset)
                    original_save = store.save

                    def save():
                        if store.meta.get('current_chunk') is None and fault == 'database_before_cache':
                            raise OSError('injected after database commit')
                        return original_save()
                    with patch.object(store.gaps, 'apply', side_effect=injected), patch.object(store, 'save', side_effect=save):
                        try:
                            self.assertTrue(retire_replaced_worker(store, replacement, folder / 'resume.bin', boundaries.append), "retire_replaced_worker(store, replacement, folder / 'resume.bin', boundaries.append)")
                        except OSError:
                            self.assertTrue(fault != 'none', "fault != 'none'")
                        else:
                            self.assertTrue(fault == 'none', "fault == 'none'")
                    store.close()
                    store = SessionStore.load(folder)
                    expected = (1000, 7) if checkpoint else (0, 0)
                    self.assertTrue((store.meta['positions'], store.meta['tests']) == expected, "(store.meta['positions'], store.meta['tests']) == expected")
                    self.assertTrue(store.meta['current_chunk'] is None, "store.meta['current_chunk'] is None")
                    self.assertTrue(store.meta['completed_chunk_count'] == 1, "store.meta['completed_chunk_count'] == 1")
                    self.assertTrue(len(store.gaps) == int(checkpoint), 'len(store.gaps) == int(checkpoint)')
                    self.assertTrue(boundaries == ([prime + 1000] if checkpoint else []), 'boundaries == ([prime + 1000] if checkpoint else [])')
                    if checkpoint:
                        self.assertTrue((folder / 'trusted-prefix-0.bin').read_bytes() == raw, "(folder / 'trusted-prefix-0.bin').read_bytes() == raw")
                    self.assertTrue(not retire_replaced_worker(store, replacement, folder / 'resume.bin', boundaries.append), "not retire_replaced_worker(store, replacement, folder / 'resume.bin', boundaries.append)")
                    cfg = store.meta['configuration']
                    offset = expected[0]
                    new = store.bind_chunk(start=prime + offset, length=10000 - offset, worker=replacement, worker_sha256=hashlib.sha256(replacement.read_bytes()).hexdigest().upper(), profile_k=8, base_positions=offset, base_tests=expected[1], gap_min=1000, threshold_policy_sha256=cfg['threshold_policy']['sha256'], worker_source_sha256='B' * 64)
                    self.assertTrue(new['index'] == 1 and new['identity']['base_positions'] == expected[0], "new['index'] == 1 and new['identity']['base_positions'] == expected[0]")
                    store.started(123456, 'not-an-observed-process')
                    different = root / 'different.bin'
                    different.write_bytes(b'other non executable')
                    try:
                        retire_replaced_worker(store, different, folder / 'resume.bin', boundaries.append)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('live owner retired')
                    store.closed('PAUSED', 0, 0)
                    store.close()
                    checks.append(dict(trusted_checkpoint=checkpoint, fault=fault, accepted=expected))
            pin = fields(10 ** 20, 10 ** 20 + 1000)['threshold_policy']
            rebased = rebase_pin(pin, (1 << 67) - 1000, (1 << 68) + 1000)
            verify_pin(rebased)
            self.assertTrue(rebased['schema'] == pin['schema'] and len(rebased['segments']) > 2, "rebased['schema'] == pin['schema'] and len(rebased['segments']) > 2")
            args = SimpleNamespace(_threshold_pin=pin)
            reset_new_args(args, {'min_gap': 'auto'})
            self.assertTrue(args._threshold_pin is None, 'args._threshold_pin is None')
            low = dict(start=str(1 << 66), end=str((1 << 66) + 1000), **fields(1 << 66, (1 << 66) + 1000))
            dummy = SimpleNamespace(meta={'configuration': low}, original_floor=low['emit_min_gap'])
            self.assertTrue(original_emission_floor(dummy, SimpleNamespace(**{k: low[k] for k in ('min_gap', 'count_gap', 'detail_gap')})) == low['emit_min_gap'] < 954, "original_emission_floor(dummy, SimpleNamespace(**{k: low[k] for k in ('min_gap', 'count_gap', 'detail_gap')})) == low['emit_min_gap'] < 954")
