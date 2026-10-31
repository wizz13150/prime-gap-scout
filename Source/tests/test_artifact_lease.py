from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
import pgn_artifact_lease as artifacts
from pgn_native_contract import file_sha
from pgn_session import file_hash


class ArtifactLeaseTests(unittest.TestCase):
    def test_only_admitted_artifacts_reuse_a_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "worker"
            checkpoint = Path(directory) / "checkpoint"
            image.write_bytes(b"qualified image")
            checkpoint.write_bytes(b"first checkpoint")
            with patch.object(artifacts, "_hash", wraps=artifacts._hash) as hashing:
                with artifacts.ArtifactLease():
                    expected = artifacts.file_digest(image, release_artifact=True)
                    self.assertEqual(file_sha(image), expected)
                    self.assertEqual(file_hash(image), expected)
                    self.assertEqual(hashing.call_count, 1)
                    first = file_hash(checkpoint)
                    checkpoint.write_bytes(b"next checkpoint")
                    self.assertNotEqual(file_hash(checkpoint), first)
                self.assertEqual(file_hash(image), expected)
                self.assertEqual(hashing.call_count, 4)

    def test_leased_executable_can_still_launch(self):
        with artifacts.ArtifactLease():
            artifacts.file_digest(sys.executable, release_artifact=True)
            completed = subprocess.run(
                [sys.executable, "-I", "-c", "print('leased image executed')"],
                capture_output=True, timeout=15,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(b"leased image executed", completed.stdout)

    def test_mutation_is_denied_or_detected_and_lock_is_released(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "worker"
            image.write_bytes(b"one")
            with artifacts.ArtifactLease():
                artifacts.file_digest(image, release_artifact=True)
                if os.name == "nt":
                    with self.assertRaises(PermissionError):
                        image.write_bytes(b"two")
                    with self.assertRaises(PermissionError):
                        image.unlink()
                else:
                    image.write_bytes(b"different image")
                    with self.assertRaisesRegex(RuntimeError, "changed"):
                        file_sha(image)
            image.write_bytes(b"replacement after session")

    def test_exception_releases_file_handles_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "worker"
            image.write_bytes(b"one")
            with self.assertRaisesRegex(ValueError, "abort"):
                with artifacts.ArtifactLease():
                    artifacts.file_digest(image, release_artifact=True)
                    raise ValueError("abort")
            image.write_bytes(b"two")
            self.assertIsNone(artifacts._current.get())


if __name__ == "__main__":
    unittest.main()
