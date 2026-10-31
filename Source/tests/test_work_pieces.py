"""Logical ownership remains contiguous at simultaneous physical boundaries."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"frontend"))
from pgn_threshold_policy import pin_range
from pgn_threshold_pointwise import POLICY_ID
from pgn_retention_rule import DOMAIN_START, DOMAIN_END, minimum_gap, next_threshold_integer
from pgn_work_pieces import pieces, next_piece


class WorkPiecesTests(unittest.TestCase):
    def test_word_and_bit_boundaries_cover_exactly_once(self):
        boundaries=[1<<bit for bit in range(67,95)]
        boundaries += [(h+1)<<64 for h in(4,6,8,10,15,21,31,54210,(1<<30)+3)]
        for boundary in boundaries:
            pin=pin_range(boundary-10000,boundary+10000,policy_id=POLICY_ID)
            cursor=boundary-10000
            for part in pieces(pin,4096):
                self.assertEqual(part.start,cursor)
                self.assertGreater(part.end,part.start)
                self.assertEqual(part.high_word,(part.end-1)>>64)
                self.assertEqual(part.bits,(part.end-1).bit_length())
                if part.kind=="exact_short_prefix":self.assertLess(part.end-part.start,30)
                self.assertEqual(part.minimum_gap,minimum_gap(part.start))
                self.assertEqual(part.minimum_gap,minimum_gap(part.end-1))
                cursor=part.end
            self.assertEqual(cursor,boundary+10000)

    def test_threshold_boundary_is_not_crossed_by_a_native_piece(self):
        for gap in range(938,1350,2):
            boundary=next_threshold_integer(gap)
            if not DOMAIN_START<boundary<DOMAIN_END:continue
            pin=pin_range(boundary-127,boundary+127,policy_id=POLICY_ID)
            parts=list(pieces(pin,10000))
            self.assertIn(boundary,[p.end for p in parts])
            self.assertEqual(parts[0].minimum_gap,gap)
            self.assertEqual(parts[-1].minimum_gap,gap+2)

    def test_full_domain_plan_is_lazy(self):
        pin=pin_range(DOMAIN_START,DOMAIN_END,policy_id=POLICY_ID)
        plan=pieces(pin,64_000_000_000_000)
        first=next(plan)
        self.assertEqual(first.start,DOMAIN_START)
        self.assertEqual(first.kind,"exact_short_prefix")
        last=next_piece(pin,DOMAIN_END-1,64_000_000_000_000)
        self.assertEqual(last.end,DOMAIN_END)
        self.assertTrue(last.tail_clipped)


if __name__=="__main__":unittest.main()
