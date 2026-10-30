from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
from pgn_compute_eta import forecast_seconds
from pgn_publications import WorkRates


class ComputeEtaTests(unittest.TestCase):
    def state(self, **changes):
        state = dict(start=2 * 10**28, end=2 * 10**28 + 10**15,
                     position=10**15 - 10**12, status="SEARCHING", speed_rate=10**12,
                     rate=1, elapsed=20 * 3600, paused_seconds=19 * 3600)
        state.update(changes)
        return state

    def test_near_end_ignores_twenty_hours_of_error_and_pause_wall(self):
        self.assertEqual(forecast_seconds(self.state()), 1)

    def test_two_restarts_do_not_dilute_current_window(self):
        rates = WorkRates()
        rates.add([(0, 0, 0), (50 * 10**9, 5 * 10**12, 10**13)])
        for _ in range(2):
            rates.begin_instance()
            self.assertIsNone(forecast_seconds(self.state(**rates.view())))
        rates.add([(100 * 10**9, 0, 0), (101 * 10**9, 10**12, 2 * 10**12)])
        view = rates.view()
        self.assertEqual(view["observed_active_seconds"], 1)
        self.assertEqual(view["average_rate"], 10**12)
        self.assertEqual(forecast_seconds(self.state(**view)), 1)

    def test_paused_failed_initializing_and_stopped_have_no_running_eta(self):
        for status in ("PAUSED", "FAILED", "PREPARING", "STOPPED", "PAUSING"):
            with self.subTest(status=status):
                self.assertIsNone(forecast_seconds(self.state(status=status)))

    def test_unknown_current_rate_does_not_fall_back_to_lifetime_average(self):
        self.assertIsNone(forecast_seconds(self.state(eta_rate=None)))
        self.assertIsNone(forecast_seconds(self.state(speed_rate=None)))

    def test_exact_remaining_tail_at_95_bits(self):
        self.assertEqual(forecast_seconds(self.state(position=10**15 - 1000, speed_rate=1000)), 1)

    def test_completed_and_invalid_counters_remain_distinct(self):
        self.assertEqual(forecast_seconds(self.state(status="COMPLETE", position=10**15)), 0)
        self.assertIsNone(forecast_seconds(self.state(status="COMPLETE", position=10**15 + 1)))
        self.assertIsNone(forecast_seconds(self.state(speed_rate=0)))


if __name__ == "__main__":
    unittest.main()
