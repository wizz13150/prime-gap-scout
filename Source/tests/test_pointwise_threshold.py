"""Exact transition ownership and immutable historical threshold pins."""
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
import pgn_threshold_policy as policy
from pgn_retention_rule import DOMAIN_START, DOMAIN_END, minimum_gap, next_threshold_integer
from pgn_threshold_pointwise import POLICY_ID, _sha


class PointwiseThresholdTests(unittest.TestCase):
    def test_known_decimal_starts(self):
        for position, expected in ((10**20,946),(15*10**19,954),(19*10**19,958),
                                   (2*10**20,960),(10**24,1134),(2*10**28,1336)):
            pin=policy.pin_range(position,position+10000,policy_id=POLICY_ID)
            self.assertEqual(policy.at_position(pin,position)["base_gap"],expected)
            self.assertEqual(policy.verify_pin(pin),pin)

    def test_every_threshold_changes_by_exactly_two_with_no_hole(self):
        checked=0
        for gap in range(minimum_gap(DOMAIN_START),minimum_gap(DOMAIN_END-1),2):
            transition=next_threshold_integer(gap)
            if not DOMAIN_START<transition<DOMAIN_END:continue
            pin=policy.pin_range(transition-1,transition+1,policy_id=POLICY_ID)
            self.assertEqual(policy.at_position(pin,transition-1)["base_gap"],gap)
            self.assertEqual(policy.at_position(pin,transition)["base_gap"],gap+2)
            self.assertEqual(pin["segments"][0]["end"],str(transition))
            checked+=1
        self.assertGreater(checked,200)

    def test_full_domain_is_bounded_contiguous_and_bit_scoped(self):
        pin=policy.pin_range(DOMAIN_START,DOMAIN_END,policy_id=POLICY_ID)
        policy.verify_pin(pin,DOMAIN_START,DOMAIN_END)
        self.assertLessEqual(len(pin["segments"]),256)
        cursor=DOMAIN_START
        for segment in pin["segments"]:
            self.assertEqual(int(segment["start"]),cursor)
            cursor=int(segment["end"])
            self.assertEqual((cursor-1).bit_length(),segment["bits"])
        self.assertEqual(cursor,DOMAIN_END)
        self.assertEqual({s["bits"]for s in pin["segments"]},set(range(67,96)))

    def test_rehashed_inconsistent_threshold_is_rejected(self):
        pin=policy.pin_range(15*10**19,15*10**19+10**6,policy_id=POLICY_ID)
        damaged=copy.deepcopy(pin)
        damaged["segments"][0]["base_gap"]+=2
        damaged.pop("sha256")
        damaged["sha256"]=_sha(damaged)
        with self.assertRaises(ValueError):policy.verify_pin(damaged)

    def test_v1_sessions_keep_their_saved_threshold(self):
        start=10**20
        historical=policy.pin_range(start,start+10**6)
        self.assertEqual(historical["schema"],"PGN_THRESHOLD_POLICY_V1")
        self.assertEqual(policy.at_position(historical,start)["base_gap"],954)
        self.assertEqual(policy.at_position(policy.pin_range(start,start+10**6,policy_id=POLICY_ID),start)["base_gap"],946)
        self.assertEqual(policy.verify_pin(historical),historical)

    def test_overrides_change_emission_floor_without_changing_base_rule(self):
        start=2*10**28
        pin=policy.pin_range(start,start+10**6,count_override=1000,detail_override=938,policy_id=POLICY_ID)
        segment=policy.at_position(pin,start)
        self.assertEqual((segment["base_gap"],segment["count_gap"],segment["detail_gap"],segment["effective_gap_min"]),(1336,1000,938,938))
        for bad in (True,937,"auto"):
            with self.assertRaises(ValueError):policy.pin_range(start,start+10**6,count_override=bad,policy_id=POLICY_ID)


if __name__=="__main__":unittest.main()
