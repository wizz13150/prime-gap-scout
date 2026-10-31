"""Timing evidence from a different native word must never seed the displayed ETA."""
from pathlib import Path
import sys
import unittest
F = Path(__file__).resolve().parents[1] / 'frontend'
sys.path.insert(0, str(F))
from pathlib import Path
import tempfile, datetime as dt, hashlib
from pgn_native_contract import fields
from pgn_range_eta import measurement, estimate, retain

class EtaScopeTests(unittest.TestCase):

    def test_contract(self):
        """Timing evidence from a different native word must never seed the displayed ETA."""
        now = dt.datetime.now(dt.timezone.utc)
        gpu = 'cpu-only-evidence-test'
        with tempfile.TemporaryDirectory(prefix='scout-eta-domain-') as temporary:
            worker = Path(temporary) / 'not-executed.bin'
            worker.write_bytes(b'hash-bound worker fixture')
            sha = hashlib.sha256(worker.read_bytes()).hexdigest().upper()

            def cfg(start, end):
                return dict(start=str(start), end=str(end), gpu=0, profile='64', worker=str(worker), **fields(start, end, 1000))

            def sample(c):
                return measurement(gpu_uuid=gpu, worker_sha256=sha, profile_k=64, configuration=c, positions=10000, seconds=10, observed_utc=now.isoformat(), source='synthetic CPU test, no performance claim', closed=True)
            a = cfg(10 ** 20, 10 ** 20 + 10000)
            b = cfg(2 * 10 ** 20, 2 * 10 ** 20 + 10000)
            sa, sb = (sample(a), sample(b))
            self.assertTrue(sa and sb and (sa['domain'] != sb['domain']), "sa and sb and (sa['domain'] != sb['domain'])")
            history = retain(retain([], sa), sb)
            self.assertTrue(len(history) == 2, 'len(history) == 2')
            ctx = {'gpu_uuid': gpu, 'gpu_index': 0, 'native_identity': {'worker_sha256': sha, 'profile_k': 64}, 'eta_evidence': {'gpu_uuid': gpu, 'history': history}}
            for c, s in ((a, sa), (b, sb)):
                result = estimate(c['start'], c['end'], c, ctx, now)
                self.assertTrue(result['available'] and result['seconds'] == 10, "result['available'] and result['seconds'] == 10")
            ctx['eta_evidence']['history'] = [sa]
            self.assertTrue(not estimate(b['start'], b['end'], b, ctx, now)['available'], "not estimate(b['start'], b['end'], b, ctx, now)['available']")
            ctx['eta_evidence']['history'] = [{**sb, 'domain': 'H10'}]
            self.assertTrue(not estimate(b['start'], b['end'], b, ctx, now)['available'], "not estimate(b['start'], b['end'], b, ctx, now)['available']")
            wide = cfg((1 << 67) - 10000, (1 << 67) + 10000)
            self.assertTrue(not estimate(wide['start'], wide['end'], wide, ctx, now)['available'], "not estimate(wide['start'], wide['end'], wide, ctx, now)['available']")
            low = dict(start=str(1 << 66), end=str((1 << 66) + 10000), **fields(1 << 66, (1 << 66) + 10000))
            self.assertTrue(sample(low), 'sample(low)')
