from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from pgn_console_window import Rectangle,contained_rectangle


class ConsoleBoundsTests(unittest.TestCase):
    def test_whole_window_fits_work_area_for_all_origins_sizes_and_edges(self):
        for work in (Rectangle(0,0,1920,1040),Rectangle(-1920,40,0,1080),Rectangle(1920,-1080,3200,-40),Rectangle(0,60,1280,720)):
            for width,height in ((1180,560),(1180,840),(2400,1600),(100,100)):
                for left,top in ((work.left-100,work.top-100),(work.right-10,work.bottom-10),(work.left+20,work.top+20)):
                    with self.subTest(work=work,width=width,height=height,left=left,top=top):
                        out=contained_rectangle(Rectangle(left,top,left+width,top+height),work)
                        self.assertGreaterEqual(out.left,work.left);self.assertGreaterEqual(out.top,work.top)
                        self.assertLessEqual(out.right,work.right);self.assertLessEqual(out.bottom,work.bottom)
                        if width<=work.width:self.assertEqual(out.width,width)
                        if height<=work.height:self.assertEqual(out.height,height)
                        self.assertEqual(contained_rectangle(out,work),out)
