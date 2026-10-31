"""The public parser must admit every word/bit boundary in the supported logical domain."""
from pathlib import Path
import sys
import unittest
F = Path(__file__).resolve().parents[1] / 'frontend'
sys.path.insert(0, str(F))
import pgn68

class LogicalRangeTests(unittest.TestCase):

    def test_contract(self):
        """The public parser must admit every word/bit boundary in the supported logical domain."""
        cases = []
        for bits in range(67, 96):
            low = 1 << bits - 1
            high = 1 << bits
            for start, end in ((low, low + 12000), (high - 12000, high)):
                parser = pgn68.argument_parser()
                args = parser.parse_args(['--start', str(start), '--end', str(end)])
                self.assertTrue(pgn68.validate_range(args, parser) == end, 'pgn68.validate_range(args, parser) == end')
                self.assertTrue(args._threshold_pin['policy_id'] == 'POINTWISE_RETAINED_MERIT_20_5', "args._threshold_pin['policy_id'] == 'POINTWISE_RETAINED_MERIT_20_5'")
                cases.append((bits, str(start), str(end)))
            if bits < 95:
                start, end = (high - 12000, high + 12000)
                parser = pgn68.argument_parser()
                args = parser.parse_args(['--start', str(start), '--end', str(end)])
                self.assertTrue(pgn68.validate_range(args, parser) == end, 'pgn68.validate_range(args, parser) == end')
                self.assertTrue(len({s['bits'] for s in args._threshold_pin['segments']}) == 2, "len({s['bits'] for s in args._threshold_pin['segments']}) == 2")
                cases.append((bits, str(start), str(end)))
        parser = pgn68.argument_parser()
        args = parser.parse_args(['--start', str(1 << 66), '--length', '1', '--min-gap', '938'])
        self.assertTrue(pgn68.validate_range(args, parser) == (1 << 66) + 1, 'pgn68.validate_range(args, parser) == (1 << 66) + 1')
