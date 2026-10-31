"""Piece counters reset; an unchanged resident epoch retains only active-time samples."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from pgn_publications import WorkRates
class ResidentRateTests(unittest.TestCase):
 def test_handoff_time_is_excluded_and_counter_reset_keeps_window(self):
  rates=WorkRates();rates.begin_piece();rates.add([(0,0,0),(1000000000,100,50),(2000000000,200,100)])
  rates.begin_piece(preserve_window=True)
  self.assertEqual(rates.view()['average_rate'],100)
  rates.add([(100000000000,0,0),(101000000000,200,100)])
  self.assertAlmostEqual(rates.view()['average_rate'],400/3)
  self.assertEqual(rates.view()['observed_active_seconds'],3)
  self.assertEqual(rates.view()['speed_rate'],200)
 def test_changed_epoch_does_not_reuse_old_rate(self):
  rates=WorkRates();rates.add([(0,0,0),(1000000000,100,50)])
  rates.begin_piece(preserve_window=False)
  self.assertIsNone(rates.view()['average_rate'])
  rates.add([(100000000000,0,0),(101000000000,20,10)])
  self.assertEqual(rates.view()['average_rate'],20)
if __name__=='__main__':unittest.main()
