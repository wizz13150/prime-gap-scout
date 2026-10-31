"""The live progress title must follow its controlled session, not a saved view."""

from pathlib import Path
import io
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
from rich.console import Console
from pgn_ui_views import render_main
from pgn_ui_workflow import phase


class LiveMenuStatusTests(unittest.TestCase):
    def title(self, outer, active, running):
        context = dict(
            status=outer,
            active_session=dict(status=active, job_active=running,
                                start=160000000000000000000,
                                end=160100000000000000000, position=2000000000000000),
            _ui_state={}, _view_width=139, _view_height=37,
        )
        stream = io.StringIO()
        Console(file=stream, width=139, height=37, color_system=None).print(render_main(context))
        return phase(context), stream.getvalue()

    def test_running_session_overrides_a_stale_failed_view(self):
        status, rendered = self.title("FAILED", "SEARCHING", True)
        self.assertEqual(status, "SEARCHING")
        self.assertIn("Current search · Searching", rendered)
        self.assertNotIn("Current search · Failed", rendered)

    def test_actual_failure_is_not_hidden_by_an_old_running_view(self):
        status, rendered = self.title("SEARCHING", "FAILED", False)
        self.assertEqual(status, "FAILED")
        self.assertIn("Current search · Failed", rendered)

    def test_pause_overrides_a_stale_running_view(self):
        status, rendered = self.title("SEARCHING", "PAUSED", False)
        self.assertEqual(status, "PAUSED")
        self.assertIn("Current search · Paused", rendered)

    def test_standalone_failure_without_a_controlled_session_remains_visible(self):
        self.assertEqual(phase({"status": "FAILED"}), "FAILED")
