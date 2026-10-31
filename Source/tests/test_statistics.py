"""Range-wide counts survive checkpoint replay and conservative rollback."""
from pathlib import Path
import math
import json
import hashlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
from pgn_index import GapIndex
from pgn_statistics import saved_range_preview, statistics_rows


class StatisticsTests(unittest.TestCase):
    def test_saved_preview_reads_matching_committed_prefix_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);start=10**20
            config=dict(start=str(start),end=str(start+10**9),count_gap=954,detail_gap=954,bins=100,target_merit=32)
            digest=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(",",":")).encode()).hexdigest()
            path=root/"session-index.sqlite3";index=GapIndex(path,"preview-test",config,digest)
            try:
                index.apply(dict(type="gap",lower=start+1,upper=start+1001,sequence=1),1)
                index.apply(dict(type="progress",positions=10**6,tests=12345,sequence=2),2)
            finally:index.db.close()
            before=path.read_bytes();view=saved_range_preview(root,config)
            self.assertEqual((view["position"],view["tests"],view["gap_count"]),(10**6,12345,1))
            self.assertEqual(view["range_statistics"]["count_total"],1)
            self.assertEqual(path.read_bytes(),before)
            with self.assertRaises(ValueError):saved_range_preview(root,dict(config,end=str(start+2*10**9)))
            self.assertEqual(path.read_bytes(),before)

    def test_old_histogram_is_unknown_until_resume_not_a_false_zero(self):
        legacy=dict(count_total=7,threshold_counts={"954":7,"1000":3},merit_band_counts=None,at_or_above_target=None)
        rows=statistics_rows(legacy,32)
        self.assertIn(("Larger gaps",7,False),rows)
        self.assertIn(("Resume to load bands",None,False),rows)
        self.assertFalse(any(label=="m >= 32" and count==0 for label,count,section in rows))

    def test_full_index_replay_rollback_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            start = 10**20
            config = dict(start=str(start), end=str(start+10**9), count_gap=954,
                          detail_gap=954, bins=100, target_merit=23.5)
            path = Path(directory) / "index.sqlite3"
            index = GapIndex(path, "statistics-test", config, "test-binding")
            pairs = [(start+i*10000, 954+i*2) for i in range(102)]

            def check(expected):
                view = index.projection.value
                self.assertEqual(view["count_total"], len(expected))
                self.assertEqual(sum(view["merit_band_counts"].values())+
                                 view["at_or_above_target"], len(expected))
                for band, count in view["merit_band_counts"].items():
                    self.assertEqual(count, sum(int(band) <= gap/math.log(low) <
                        min(int(band)+1, 23.5) for low, gap in expected))
                self.assertEqual(view["at_or_above_target"],
                                 sum(gap/math.log(low) >= 23.5 for low, gap in expected))

            try:
                for sequence, (low, gap) in enumerate(pairs, 1):
                    index.apply(dict(type="gap", lower=low, upper=low+gap,
                                     sequence=sequence), sequence)
                check([])
                index.apply(dict(type="progress", positions=10**9, tests=1, sequence=103), 103)
                check(pairs)
                low, gap = pairs[0]
                index.apply(dict(type="gap", lower=low, upper=low+gap, sequence=104), 104)
                check(pairs)
                index.apply(dict(type="rewind", positions=50*10000, tests=1, sequence=105), 105)
                check(pairs[:50])
                index.db.close()
                index = GapIndex(path, "statistics-test", config, "test-binding")
                check(pairs[:50])
                index.apply(dict(type="progress", positions=10**9, tests=1, sequence=106), 106)
                check(pairs)
            finally:
                index.db.close()


if __name__ == "__main__":
    unittest.main()
