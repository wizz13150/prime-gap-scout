"""The added statistics panel must not remove the familiar dashboard frames."""
from pathlib import Path
import importlib.util,io,sys,unittest,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))

@unittest.skipUnless(importlib.util.find_spec('rich'),'Rich renderer dependency')
class DashboardSkinTests(unittest.TestCase):
    def test_original_hud_frames_and_three_result_panels(self):
        from rich.console import Console
        from pgn_dashboard import render
        start=2*10**28
        state=dict(start=start,end=start+10**12,position=10**12,tests=100,status='COMPLETE',minimum_gap=1332,target_merit=32,display_rows=10,
            gaps=[(1332,1332/math.log(start+1),start+1)],range_statistics=dict(count_total=1,threshold_counts={'1332':1,'1400':0},merit_band_counts={'20':1},at_or_above_target=0,statistics_target=32))
        out=io.StringIO();Console(file=out,width=150,height=46,safe_box=False,legacy_windows=False,color_system=None).print(render(state,150,46))
        lines=out.getvalue().splitlines()
        metrics=next(line for line in lines if 'Speed'in line and 'Tests/s'in line)
        self.assertEqual(metrics.count('╭'),4)
        self.assertTrue(any('DEVICE & RANGE'in line and '╭'in line for line in lines))
        results=next(line for line in lines if 'BEST 10'in line and 'RECENT 10'in line and 'STATISTICS'in line)
        self.assertEqual(results.count('╭'),3)
        self.assertTrue(any('RANGE PROGRESS'in line and '╭'in line for line in lines))
        self.assertIn(str(start+1),out.getvalue())

if __name__=='__main__':unittest.main()
