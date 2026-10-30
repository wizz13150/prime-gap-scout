"""Completion publication failures must never invent success or restart work."""
from pathlib import Path
import ast
import errno
import ctypes
import json
import os
import sys
import tempfile
import textwrap
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
import pgn_detached_worker as worker


class CompletionPublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.owner = object.__new__(worker.DetachedWindowsProcess)
        self.owner.root = Path(self.directory.name)
        self.owner.token = "a" * 32
        self.owner.image_sha256 = "b" * 64
        self.owner.returncode = None
        self.owner._done_result = None
        self.owner._publication_error_since = None
        self.owner._completion_lock = threading.RLock()
        self.owner._handle = None
        self.owner.stdout = Mock()
        self.owner.controller = Mock()
        self.owner.controller.poll.return_value = None
        self.result = dict(token=self.owner.token, image_sha256=self.owner.image_sha256,
                           closed=True, started=True, error=None, exit=0)
        self.done = self.owner.root / "done.json"
        self.done.write_text(json.dumps(self.result), encoding="utf-8")

    def test_transient_permission_does_not_end_or_restart_worker(self):
        with patch.object(worker, "load", side_effect=[PermissionError("busy"), PermissionError("busy"), self.result]):
            self.assertIsNone(self.owner.poll())
            self.assertIsNone(self.owner.poll())
            self.assertEqual(self.owner.poll(), 0)
        self.assertFalse((self.owner.root / "terminate.request").exists())

    def test_accepted_completion_is_cached_even_if_file_becomes_unreadable(self):
        self.assertEqual(self.owner.poll(), 0)
        self.done.unlink()
        with patch.object(worker, "load", side_effect=AssertionError("must not reopen")):
            self.assertEqual(self.owner.poll(), 0)
            self.owner.close()
        self.owner.stdout.close.assert_called_once()

    def test_persistent_denial_has_a_bounded_explicit_failure(self):
        with patch.object(worker, "load", side_effect=PermissionError("ACL")), patch.object(worker.time, "monotonic", side_effect=[10, 16]):
            self.assertIsNone(self.owner.poll())
            with self.assertRaisesRegex(RuntimeError, "closure is unconfirmed"):
                self.owner.poll()
        self.assertIsNone(self.owner.returncode)

    def test_missing_receipt_is_normal_while_owner_lives(self):
        self.done.unlink()
        self.assertIsNone(self.owner.poll())
        self.assertIsNone(self.owner._publication_error_since)

    def test_dead_owner_without_receipt_never_invents_success(self):
        self.done.unlink()
        self.owner.controller.poll.return_value = 0
        with patch.object(worker.time, "monotonic", side_effect=[10, 16]):
            self.assertIsNone(self.owner.poll())
            with self.assertRaisesRegex(RuntimeError, "unconfirmed"):
                self.owner.poll()

    def test_token_and_image_identity_remain_mandatory(self):
        for field in ("token", "image_sha256"):
            with self.subTest(field=field):
                changed = dict(self.result, **{field: "c" * len(self.result[field])})
                with patch.object(worker, "load", return_value=changed), self.assertRaises(RuntimeError):
                    self.owner.poll()
                self.assertIsNone(self.owner.returncode)

    def test_incomplete_closure_and_boolean_exit_do_not_become_success(self):
        for change in ({"closed": False}, {"started": False}, {"error": "failed"}, {"exit": True}):
            with self.subTest(change=change):
                self.owner.returncode = None
                with patch.object(worker, "load", return_value=dict(self.result, **change)):
                    self.assertEqual(self.owner.poll(), 1)

    def test_nonsharing_io_errors_fail_immediately(self):
        with patch.object(worker, "load", side_effect=OSError(errno.EIO, "disk error")), self.assertRaises(OSError):
            self.owner.poll()

    def test_malformed_receipt_is_not_a_temporary_permission_race(self):
        self.done.write_text("{broken", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            self.owner.poll()

    def test_writer_retries_only_the_same_fsynced_receipt(self):
        replace = worker.os.replace
        attempts = []
        def publish(source, target):
            attempts.append(Path(source).read_bytes())
            if len(attempts) < 3:
                raise PermissionError("temporary sharing violation")
            replace(source, target)
        with patch.object(worker.os, "replace", side_effect=publish), patch.object(worker.time, "sleep"):
            worker.atomic(self.done, self.result)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(len(set(attempts)), 1)
        self.assertEqual(json.loads(self.done.read_text()), self.result)

    def test_persistent_writer_denial_keeps_pending_receipt(self):
        with patch.object(worker.os, "replace", side_effect=PermissionError("ACL")), patch.object(worker.time, "monotonic", side_effect=[10, 16]), self.assertRaises(PermissionError):
            worker.atomic(self.done, self.result)
        self.assertTrue(self.done.with_suffix(".json.pending").exists())

    def test_owner_wait_error_is_not_reported_as_a_clock_error(self):
        source = (Path(worker.__file__).parent / "pgn_engine.py").read_text(encoding="utf-8")
        nodes = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)
                 and n.name == "observe" and [a.arg for a in n.args.args] == ["current", "current_clock"]]
        self.assertEqual(len(nodes), 1)
        events, failures, done = [], [], threading.Event()
        scope = dict(watcher_errors=failures, enqueue=events.append, watcher_done=done)
        exec(compile(textwrap.dedent(ast.get_source_segment(source, nodes[0])), "actual-owner-observer", "exec"), scope)
        process, clock = Mock(), Mock()
        process.wait.side_effect = PermissionError("completion unavailable")
        scope["observe"](process, clock)
        self.assertEqual(events[0][0], "owner_wait_error")
        clock.finish.assert_not_called()
        self.assertTrue(done.is_set())

    @unittest.skipUnless(os.name == "nt", "Windows sharing contract")
    def test_actual_windows_exclusive_lock_does_not_abort_poll(self):
        from ctypes import wintypes as types
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [types.LPCWSTR, types.DWORD, types.DWORD, ctypes.c_void_p, types.DWORD, types.DWORD, types.HANDLE]
        kernel.CreateFileW.restype = types.HANDLE
        kernel.CloseHandle.argtypes = [types.HANDLE]
        handle = kernel.CreateFileW(str(self.done), 0x80000000, 0, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            self.assertIsNone(self.owner.poll())
            self.assertIsNotNone(self.owner._publication_error_since)
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual(self.owner.poll(), 0)

    @unittest.skipUnless(os.name == "nt", "Windows replacement sharing contract")
    def test_actual_windows_exclusive_lock_during_publication(self):
        from ctypes import wintypes as types
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [types.LPCWSTR, types.DWORD, types.DWORD, ctypes.c_void_p, types.DWORD, types.DWORD, types.HANDLE]
        kernel.CreateFileW.restype = types.HANDLE
        kernel.CloseHandle.argtypes = [types.HANDLE]
        handle = kernel.CreateFileW(str(self.done), 0x80000000, 0, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        release = threading.Timer(0.1, lambda: kernel.CloseHandle(handle))
        release.start()
        try:
            worker.atomic(self.done, dict(self.result, exit=7))
        finally:
            release.join()
        self.assertEqual(json.loads(self.done.read_text())["exit"], 7)

    def test_ui_and_lifetime_watcher_share_one_final_transition(self):
        calls = 0
        def load_once(path):
            nonlocal calls
            calls += 1
            worker.time.sleep(0.001)
            if calls < 8:
                raise PermissionError("sharing race")
            return self.result
        def reader():
            for index in range(40):
                value = self.owner.poll()
                if value is not None:
                    return value
            self.fail("completion never admitted")
        with patch.object(worker, "load", side_effect=load_once), ThreadPoolExecutor(max_workers=2) as threads:
            a, b = threads.submit(reader), threads.submit(reader)
            self.assertEqual((a.result(), b.result()), (0, 0))
        self.assertEqual(calls, 8)
        self.assertIsNone(self.owner._publication_error_since)


if __name__ == "__main__":
    unittest.main(verbosity=2)
