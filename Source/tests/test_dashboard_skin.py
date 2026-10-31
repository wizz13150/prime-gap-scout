"""The added statistics panel must not remove the familiar dashboard frames."""
from pathlib import Path
import importlib.util,io,sys,unittest,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))

@unittest.skipUnless(importlib.util.find_spec('rich'),'Rich renderer dependency')
class DashboardSkinTests(unittest.TestCase):
    def test_idle_lower_counts_use_complete_saved_projection_not_visible_rows(self):
        from rich.console import Console
        from pgn_dashboard import render
        start=150000000000000000000
        state=dict(start=start,end=start+10**17,position=723520626360300,tests=1859322942525,
            status='Idle',minimum_gap=960,target_merit=32,display_rows=10,gap_count=2299,
            gaps=[(1320,1320/math.log(start+1),start+1)],
            range_statistics=dict(count_total=2299,threshold_counts={'960':2299,'1000':871,'1100':69,'1200':6,'1300':1,'1400':0,'1500':0},merit_band_counts={'20':2299},at_or_above_target=0,statistics_target=32))
        out=io.StringIO();Console(file=out,width=168,height=48,safe_box=False,legacy_windows=False,color_system=None).print(render(state,168,48))
        lower=out.getvalue().split('CUMULATIVE COUNTS',1)[1]
        self.assertRegex(lower,r'≥1000\s+871')
        self.assertRegex(lower,r'≥1100\s+69')

    def test_original_hud_frames_and_three_result_panels(self):
        from rich.console import Console
        from pgn_dashboard import render
        start=2*10**28
        state=dict(start=start,end=start+10**12,position=10**12,tests=100,status='COMPLETE',minimum_gap=1332,target_merit=32,display_rows=10,
            gaps=[(1332,1332/math.log(start+1),start+1)],range_statistics=dict(count_total=1,threshold_counts={'1332':1,'1400':0},merit_band_counts={'20':1},at_or_above_target=0,statistics_target=32))
        out=io.StringIO();Console(file=out,width=168,height=48,safe_box=False,legacy_windows=False,color_system=None).print(render(state,168,48))
        lines=out.getvalue().splitlines()
        metrics=next(line for line in lines if 'Speed'in line and 'Tests/s'in line)
        self.assertEqual(metrics.count('╭'),4)
        self.assertTrue(any('DEVICE & RANGE'in line and '╭'in line for line in lines))
        results=next(line for line in lines if 'BEST 10'in line and 'RECENT 10'in line and 'STATISTICS'in line)
        self.assertEqual(results.count('╭'),3)
        self.assertTrue(any('CUMULATIVE COUNTS'in line and '╭'in line for line in lines))
        self.assertIn(str(start+1),out.getvalue())

    def test_balanced_panels_preserve_full_primes_and_lower_cumulative_counts(self):
        from rich.console import Console
        from pgn_dashboard import render
        for start,width,rows,height in [(10**20,150,10,48),(2*10**28,168,10,48),(2*10**28,168,30,64)]:
            with self.subTest(start=start,width=width,rows=rows):
                bounds=[960,1000,1100,1200,1300,1400,1500]
                gaps=[(1500+i*2,(1500+i*2)/math.log(start+1+i*10000),start+1+i*10000) for i in range(rows)]
                state=dict(start=start,end=start+10**12,position=10**12,tests=1234567890123,status='COMPLETE',
                    minimum_gap=960,target_merit=32,display_rows=rows,gaps=gaps,gap_count=rows,
                    gap_threshold_counts={n:rows for n in bounds},range_statistics=dict(count_total=rows,
                    threshold_counts={str(n):rows for n in bounds},merit_band_counts={str(n):1 for n in range(20,32)},
                    at_or_above_target=2,statistics_target=32))
                out=io.StringIO();Console(file=out,width=width,height=height,safe_box=False,legacy_windows=False,color_system=None).print(render(state,width,height))
                text=out.getvalue();lines=text.splitlines()
                header=next(line for line in lines if 'BEST '+str(rows) in line and 'STATISTICS'in line)
                left=[i for i,c in enumerate(header) if c=='╭'];right=[i for i,c in enumerate(header) if c=='╮']
                self.assertEqual((len(left),len(right)),(3,3))
                widths=[r-l+1 for l,r in zip(left,right)]
                self.assertLessEqual(max(widths)-min(widths),1,widths)
                for gap,merit,lower in gaps:self.assertIn(str(lower),text)
                lower=text.split('CUMULATIVE COUNTS',1)[1]
                self.assertIn('Positions',lower);self.assertIn('Tests',lower)
                for n in bounds:self.assertIn('≥'+str(n),lower)
                self.assertNotIn('Terminal size',text)
                self.assertLessEqual(len(lines),height)

    def test_compact_height_and_footer_hitboxes_at_each_rows_setting(self):
        from rich.console import Console
        from pgn_dashboard import render
        from console_ui import Dashboard
        for start in (15*10**19, 2*10**28):
            heights=[]
            for rows in (10,15,20,30):
                with self.subTest(start=start,rows=rows):
                    gaps=[(1600+2*i,(1600+2*i)/math.log(start+1+i*10000),start+1+i*10000)for i in range(rows)]
                    state=dict(start=start,end=start+10**16,position=10**12,tests=100,status='SEARCHING',
                        minimum_gap=960,target_merit=32,display_rows=rows,gaps=gaps,gap_count=rows,
                        range_statistics=dict(count_total=rows,threshold_counts={'960':rows,'1000':rows,'1100':rows,'1200':rows,'1300':rows,'1400':rows,'1500':rows},
                            merit_band_counts={str(i):1 for i in range(20,32)},at_or_above_target=2,statistics_target=32))
                    layout=render(state,168,80);height=layout.pgn_content_height;heights.append(height)
                    output=io.StringIO();Console(file=output,width=168,height=height,safe_box=False,legacy_windows=False,color_system=None).print(layout)
                    lines=output.getvalue().splitlines()
                    self.assertEqual(len(lines),height)
                    self.assertTrue(any('GAP SIZE'in line and 'MERIT'in line for line in lines))
                    for _,_,lower in gaps:self.assertIn(str(lower),output.getvalue())
                    self.assertLessEqual(height,21+max(rows+5,16))
                    for region in layout.pgn_hit_regions:
                        self.assertGreaterEqual(region['y'],height-3)
                        self.assertLess(region['y']+region['height'],height+1)
                    # The real ANSI dashboard must stop at the natural footer,
                    # even when the terminal offers a much taller viewport.
                    stream=io.StringIO();dashboard=Dashboard(stream);dashboard._dimensions=lambda:(168,80)
                    dashboard.update(state,force=True)
                    self.assertEqual(len(dashboard._previous),height)
                    dashboard.finish()
            self.assertEqual(heights,sorted(heights))
            self.assertGreater(heights[-1],heights[0])

    def test_startup_requests_wide_viewport_before_stacked_height(self):
        from console_ui import Dashboard
        for start in (150000000000000000000,2*10**28):
            for rows in (10,15,20,30):
                with self.subTest(start=start,rows=rows):
                    dashboard=Dashboard(writer=io.StringIO())
                    dashboard._dimensions=lambda:(100,30)
                    requests=[]
                    dashboard._fit_console_height=lambda height,columns=None: requests.append((columns,height)) or False
                    dashboard.update(dict(start=start,end=start+10**16,status='Idle',minimum_gap=960,target_merit=32,display_rows=rows),force=True)
                    self.assertEqual(len(requests),1)
                    columns,height=requests[0]
                    self.assertGreaterEqual(columns,3*(len(str(start+10**16))+24)+4)
                    self.assertLessEqual(height,21+max(rows+5,16))
                    dashboard.finish()

    def test_statistics_is_two_columns_at_exact_admission_width_empty_and_populated(self):
        from rich.console import Console
        from pgn_dashboard import render
        for start in (150000000000000000000,2*10**28):
            width=3*(len(str(start+10**16))+24)+4
            for empty in (True,False):
                with self.subTest(start=start,empty=empty):
                    state=dict(start=start,end=start+10**16,status='Idle' if empty else 'SEARCHING',minimum_gap=954,target_merit=32,display_rows=10)
                    if not empty:state['range_statistics']=dict(count_total=24,threshold_counts={'954':24,'1000':8,'1500':0},merit_band_counts={'20':10,'21':10,'22':1,'23':3},at_or_above_target=0,statistics_target=32)
                    layout=render(state,width,80);out=io.StringIO()
                    Console(file=out,width=width,height=layout.pgn_content_height,safe_box=False,legacy_windows=False,color_system=None).print(layout)
                    text=out.getvalue()
                    self.assertTrue(any('GAP SIZE' in line and 'MERIT' in line for line in text.splitlines()))
                    for b in range(20,32):self.assertIn(f'[{b}, {b+1})',text)
                    self.assertIn('Larger gaps',text)

if __name__=='__main__':unittest.main()

