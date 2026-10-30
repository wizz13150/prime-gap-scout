"""Real Windows child/job lifecycle and completion locks; never uses a GPU."""
from pathlib import Path
import ctypes
from ctypes import wintypes as types
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
from pgn_detached_worker import DetachedWindowsProcess, atomic
from pgn_owned import image_hash


@unittest.skipUnless(os.name == "nt", "Windows process and file sharing contract")
class ActualWindowsOwnerTests(unittest.TestCase):
    def test_repeated_owned_children_and_locked_final_receipts(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [types.LPCWSTR, types.DWORD, types.DWORD, ctypes.c_void_p, types.DWORD, types.DWORD, types.HANDLE]
        kernel.CreateFileW.restype = types.HANDLE
        kernel.CloseHandle.argtypes = [types.HANDLE]
        with tempfile.TemporaryDirectory(prefix="scout-owned-lifecycle-") as name:
            root = Path(name)
            child = root / "child.py"
            child.write_text("print('OWNED_CPU_FIXTURE_COMPLETE', flush=True)\n", encoding="utf-8")
            executable_hash = image_hash(sys.executable)
            for index in range(24):
                session = root / str(index)
                session.mkdir()
                command = [sys.executable, "-I", "-X", "utf8", str(child), "--state", str(session / "checkpoint"), "--stop-file", str(session / "stop")]
                process = DetachedWindowsProcess(command, dict(os.environ), "CPU-OWNER-FIXTURE", registry_root=root / "private-lease")
                try:
                    identity = session / "native-owner-current.json"
                    atomic(identity, {"pid": process.pid, "birth": process.birth,
                           "image_sha256": executable_hash, "configuration_sha256": "A" * 64,
                           "wal_sequence": index + 1, "session_id": "cpu-lifecycle-fixture"})
                    process.commit_identity(identity)
                    process.resume()
                    self.assertEqual(list(process.stdout), ["OWNED_CPU_FIXTURE_COMPLETE\n"])
                    self.assertEqual(process.controller.wait(10), 0)
                    done = process.root / "done.json"
                    handle = kernel.CreateFileW(str(done), 0x80000000, 0, None, 3, 0x80, None)
                    self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
                    self.assertIsNone(process.poll())
                    unlock = threading.Timer(0.03, lambda: kernel.CloseHandle(handle))
                    unlock.start()
                    try:
                        self.assertEqual(process.wait(10), 0)
                    finally:
                        unlock.join()
                    # Closing after an accepted receipt must use that receipt,
                    # including when another reader now locks the disk file.
                    handle = kernel.CreateFileW(str(done), 0x80000000, 0, None, 3, 0x80, None)
                    self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
                    try:
                        process.close()
                    finally:
                        kernel.CloseHandle(handle)
                    result = json.loads(done.read_text())
                    self.assertTrue(result["closed"] and result["started"])
                    self.assertIsNone(result["error"])
                    self.assertEqual(result["exit"], 0)
                except BaseException:
                    process.close(force=True)
                    raise


if __name__ == "__main__":
    unittest.main(verbosity=2)
