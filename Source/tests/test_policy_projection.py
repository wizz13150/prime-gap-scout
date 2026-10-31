"""Count and detail roles must remain distinct across threshold transitions and replay."""
from pathlib import Path
import sys
import unittest
F = Path(__file__).resolve().parents[1] / 'frontend'
sys.path.insert(0, str(F))
from pathlib import Path
import tempfile, json, hashlib
from pgn_threshold_policy import pin_range
from pgn_index import GapIndex
from types import SimpleNamespace
from pgn_output import write_index_counts, files_context, threshold_description

class PolicyProjectionTests(unittest.TestCase):

    def test_contract(self):
        """Count and detail roles must remain distinct across threshold transitions and replay."""
        start = 10 ** 20
        end = 12 * 10 ** 19
        pin = pin_range(start, end, 'auto', None, 946, policy_id='POINTWISE_RETAINED_MERIT_20_5')
        initial = pin['segments'][0]
        later = next((s for s in pin['segments'] if s['count_gap'] > 946))
        cut = int(later['start'])
        cfg = dict(start=str(start), end=str(end), min_gap=946, count_gap=946, detail_gap=946, threshold_policy=pin, bins=10, report_top=100, target_merit=32)
        digest = hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        sequence = 0
        with tempfile.TemporaryDirectory(prefix='scout-policy-projection-') as temporary:
            path = Path(temporary) / 'index.sqlite3'
            index = GapIndex(path, 'local-policy-test', cfg, digest)

            def apply(kind, **fields):
                nonlocal sequence
                sequence += 1
                index.apply(dict(sequence=sequence, type=kind, **fields), sequence * 100)
            p1 = start + 100
            p2 = cut + 100
            p3 = cut + 2000
            p4 = cut - 500
            apply('gap', lower=str(p1), upper=str(p1 + 946))
            apply('gap', lower=str(p2), upper=str(p2 + 946))
            self.assertTrue(index.policy_count('count', end) == 0, "index.policy_count('count', end) == 0")
            apply('progress', positions=end - start, tests=7)
            self.assertTrue(index.policy_count('count', end) == 1 and index.policy_count('detail', end) == 2, "index.policy_count('count', end) == 1 and index.policy_count('detail', end) == 2")
            self.assertTrue(len(index.policy_top('count', end)) == 1 and len(index.policy_top('detail', end)) == 2, "len(index.policy_top('count', end)) == 1 and len(index.policy_top('detail', end)) == 2")
            self.assertTrue(index.count_rows(946, end) == 2 and index.count_rows(948, end) == 0, 'index.count_rows(946, end) == 2 and index.count_rows(948, end) == 0')
            apply('rewind', positions=p1 + 2000 - start, tests=3)
            self.assertTrue(index.policy_count('count', end) == 1 and index.policy_count('detail', end) == 1, "index.policy_count('count', end) == 1 and index.policy_count('detail', end) == 1")
            apply('progress', positions=end - start, tests=7)
            apply('gap', lower=str(p3), upper=str(p3 + 946))
            apply('gap', lower=str(p4), upper=str(p4 + 946))
            self.assertTrue(index.policy_count('count', end) == 2 and index.policy_count('detail', end) == 4, "index.policy_count('count', end) == 2 and index.policy_count('detail', end) == 4")
            self.assertTrue(p4 in {r[2] for r in index.policy_rows('count', end)} and p2 not in {r[2] for r in index.policy_rows('count', end)}, "p4 in {r[2] for r in index.policy_rows('count', end)} and p2 not in {r[2] for r in index.policy_rows('count', end)}")
            before = dict(index.projection.value)
            apply('gap', lower=str(p3), upper=str(p3 + 946))
            self.assertTrue(index.projection.value == before, 'index.projection.value == before')
            self.assertTrue(sum(index.policy_bin_counts('count', end)) == 2 and sum(index.policy_bin_counts('detail', end)) == 4, "sum(index.policy_bin_counts('count', end)) == 2 and sum(index.policy_bin_counts('detail', end)) == 4")
            index.close()
            index = GapIndex(path, 'local-policy-test', cfg, digest)
            self.assertTrue(index.policy_count('count', end) == 2 and index.policy_count('detail', end) == 4, "index.policy_count('count', end) == 2 and index.policy_count('detail', end) == 4")
            self.assertTrue(len(index.policy_recent('count', end)) == 2 and len(index.policy_recent('detail', end)) == 4, "len(index.policy_recent('count', end)) == 2 and len(index.policy_recent('detail', end)) == 4")
            args = SimpleNamespace(start=start, count_gap=946, detail_gap=946, bins=10, target_merit=32)
            folder = Path(temporary)

            def write(path, text):
                path.write_text(text)
            exports = write_index_counts(folder, args, end, end - start, 'COMPLETE', index, write)
            self.assertTrue(exports['counts_csv'] == 'counts_policy.csv', "exports['counts_csv'] == 'counts_policy.csv'")
            self.assertTrue(sum(map(int, (folder / 'counts_policy.csv').read_text().strip().split(','))) == 2, "sum(map(int, (folder / 'counts_policy.csv').read_text().strip().split(','))) == 2")
            self.assertTrue(not (folder / 'counts_ge946.csv').exists(), "not (folder / 'counts_ge946.csv').exists()")
            self.assertTrue('counts_policy.csv' in files_context(folder, {'configuration': cfg})['files'], "'counts_policy.csv' in files_context(folder, {'configuration': cfg})['files']")
            self.assertTrue('local threshold' in threshold_description(pin, 'count', 946), "'local threshold' in threshold_description(pin, 'count', 946)")
            self.assertTrue(threshold_description(pin, 'detail', 946) == '946', "threshold_description(pin, 'detail', 946) == '946'")
            index.close()
