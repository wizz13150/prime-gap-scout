"""Startup must be visible before blocking work, from either UI entrypoint."""
from pathlib import Path
from types import SimpleNamespace
import copy,io,sys,threading,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"frontend"))
from pgn_starting import show_starting
from pgn_ui_workflow import starting_requested,pause_control


class StartingTests(unittest.TestCase):
    def args(self,**changes):
        values=dict(headless=False,ui="live",resume=None,start=150000000000000000000,
                    end=None,length=10**16,display_rows=10,target_merit=32)
        values.update(changes)
        return SimpleNamespace(**values)

    def test_initial_frame_precedes_saved_session_io_and_preserves_data(self):
        painted=[]
        class View:
            def update(self,state,force=False):painted.append(copy.deepcopy(state))
        original={"status":"Idle","_controller":threading.Lock()}
        metadata=dict(configuration=dict(start="150000000000000000000",end="150010000000000000000",target_merit=32),positions=123,tests=456)
        saved=copy.deepcopy(metadata)
        def read(folder):
            self.assertEqual(painted[0]["status"],"STARTING")
            self.assertIsNone(painted[0]["start"])
            return metadata
        show_starting(self.args(resume=Path("saved")),original,read,View)
        self.assertEqual(painted[-1]["position"],123)
        self.assertEqual(metadata,saved)
        self.assertEqual(original["status"],"Idle")

    def test_failed_resume_read_restores_console_before_propagating_error(self):
        closed=[]
        class View:
            def update(self,state,force=False):pass
            def finish(self):closed.append(True)
        def denied(folder):raise PermissionError("session unavailable")
        with self.assertRaises(PermissionError):
            show_starting(self.args(resume=Path("saved")),metadata_reader=denied,dashboard_type=View)
        self.assertEqual(closed,[True])

    def test_new_start_does_not_display_the_previous_ranges_results(self):
        frames=[]
        class View:
            def update(self,state,force=False):frames.append(state.copy())
        show_starting(self.args(),dict(position=999,tests=888,gaps=[(960,20,123)]),dashboard_type=View)
        self.assertEqual(frames[0]["status"],"STARTING")
        self.assertEqual(frames[0]["position"],0)
        self.assertEqual(frames[0]["gaps"],[])

    def test_all_start_requests_disable_duplicate_start(self):
        for kind in ("new","resume","activate_queued"):
            context=dict(status="Idle",idle_start_available=True,_ui_state=dict(pending_worker_request=dict(kind=kind)))
            self.assertTrue(starting_requested(context))
            self.assertFalse(pause_control(context)["enabled"])
        self.assertFalse(starting_requested(dict(_ui_state=dict(pending_worker_request=dict(kind="pause")))))

    def test_headless_never_constructs_a_dashboard(self):
        def forbidden():raise AssertionError("Headless UI side effect")
        self.assertIsNone(show_starting(self.args(headless=True),dashboard_type=forbidden))

    def test_menu_and_mining_headers_show_starting_for_pending_start(self):
        from rich.console import Console
        from rich.text import Text
        from pgn_ui_views import page
        from pgn_dashboard import render
        context=dict(status="Idle",start=150000000000000000000,end=150010000000000000000,
                     display_rows=10,_ui_state=dict(pending_worker_request=dict(kind="resume")))
        output=io.StringIO();console=Console(file=output,width=163,height=46,color_system=None)
        console.print(page("Search ranges",Text(""),context,Text("")))
        self.assertIn("Starting",output.getvalue())
        output.seek(0);output.truncate();console.print(render(context,163,46))
        self.assertIn("STARTING",output.getvalue())


if __name__=="__main__":unittest.main()
