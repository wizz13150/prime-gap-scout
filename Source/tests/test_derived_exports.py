import ctypes
from contextlib import closing
import errno
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
from pgn_exports import DerivedExports
from pgn68 import atomic_export_text, atomic_text


class DerivedExportTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Real Windows sharing semantics")
    def test_locked_csv_keeps_latest_export_and_durable_progress(self):
        from ctypes import wintypes as T
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [T.LPCWSTR, T.DWORD, T.DWORD, ctypes.c_void_p, T.DWORD, T.DWORD, T.HANDLE]
        kernel.CreateFileW.restype = T.HANDLE
        kernel.CloseHandle.argtypes = [T.HANDLE]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "counts.partial.csv"
            atomic_text(path, "positions,count\n1,1\n")
            handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            notices = []
            exports = DerivedExports(atomic_export_text, notices.append)
            try:
                with self.assertRaises(PermissionError):
                    atomic_text(path, "must remain strict", retry_seconds=0)
                with closing(sqlite3.connect(root / "committed.sqlite")) as db:
                    db.execute("create table progress (positions integer)")
                    for value in (2, 3):
                        db.execute("delete from progress")
                        db.execute("insert into progress values (?)", (value,))
                        db.commit()
                        self.assertFalse(exports.write(path, f"positions,count\n{value},{value}\n"))
                    self.assertEqual(db.execute("select positions from progress").fetchone()[0], 3)
                self.assertEqual(path.read_text(), "positions,count\n1,1\n")
                self.assertIn(path.name, exports.notice)
                self.assertTrue(exports.write(root / "unlocked.txt", "other report remains writable"))
            finally:
                self.assertTrue(kernel.CloseHandle(handle))
            exports.retry()
            self.assertEqual(path.read_text(), "positions,count\n3,3\n")
            self.assertEqual(exports.notice, "")
            self.assertEqual(notices[-1], "")
            self.assertEqual(list(root.glob("*.pending")), [])

    def test_disk_full_is_not_hidden(self):
        def full(path, text):
            raise OSError(errno.ENOSPC, "No space left")
        exports = DerivedExports(full)
        with self.assertRaises(OSError):
            exports.write(Path("report.csv"), "result")
        self.assertEqual(exports.notice, "")

    def test_non_windows_permission_error_remains_strict(self):
        def denied(path, text):
            raise PermissionError(errno.EACCES, "Unclassified permission error")
        exports = DerivedExports(denied)
        with self.assertRaises(PermissionError):
            exports.write(Path("report.csv"), "result")
        self.assertEqual(exports.notice, "")


if __name__ == "__main__":
    unittest.main()
