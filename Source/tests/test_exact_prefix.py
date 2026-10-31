"""Known independently proved gap fixtures exercise atomic prefix recovery; no new discovery."""
from pathlib import Path
import sys
import unittest
F = Path(__file__).resolve().parents[1] / 'frontend'
sys.path.insert(0, str(F))
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
from pgn_native_contract import fields
from pgn_session import SessionStore
from pgn_exact_prefix import certify

class FixturePrimality:
    """Independent integer-pow oracle below the deterministic MR13 bound.

    The fixture is 68 bits. This recovery test must run in a source checkout
    without installed native libraries; the shipped FLINT runtime is exercised
    separately by the frozen 95-bit integration tests.
    """

    def prime(self, number):
        if not 0 <= number < 3317044064679887385961981:
            raise ValueError("Fixture exceeds the deterministic oracle bound")
        if number < 2:
            return False
        bases = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
        if number in bases:
            return True
        if any(number % base == 0 for base in bases):
            return False
        odd = number - 1
        powers = 0
        while odd % 2 == 0:
            odd //= 2
            powers += 1
        for base in bases:
            value = pow(base, odd, number)
            if value in (1, number - 1):
                continue
            for _ in range(powers - 1):
                value = value * value % number
                if value == number - 1:
                    break
            else:
                return False
        return True

class ExactPrefixTests(unittest.TestCase):

    def test_contract(self):
        """Known independently proved gap fixtures exercise atomic prefix recovery; no new discovery."""
        proof = FixturePrimality()
        prime = 190121201168499697841
        upper = prime + 1500
        self.assertTrue(proof.prime(prime) and proof.prime(upper) and (not any((proof.prime(n) for n in range(prime + 2, upper, 2)))), 'proof.prime(prime) and proof.prime(upper) and (not any((proof.prime(n) for n in range(prime + 2, upper, 2))))')

        def oracle(end):
            lo = end - 1
            if lo % 2 == 0:
                lo -= 1
            while not proof.prime(lo):
                lo -= 2
            hi = end if end % 2 else end + 1
            while not proof.prime(hi):
                hi += 2
            return (lo, hi)
        cfg = dict(start=str(prime), end=str(prime + 10000), bins=10, target_merit=32, report_top=100, **fields(prime, prime + 10000, 1000))
        piece = SimpleNamespace(start=prime, end=prime + 10, minimum_gap=1000, policy_sha256=cfg['threshold_policy']['sha256'], kind='exact_short_prefix')
        certificate = certify(piece, oracle)
        self.assertTrue(certificate['owned_gap'] == [str(prime), str(upper)], "certificate['owned_gap'] == [str(prime), str(upper)]")

        def reject(call):
            try:
                call()
            except ValueError:
                return
            raise AssertionError('Repeated or invalid prefix accepted')
        with tempfile.TemporaryDirectory(prefix='scout-prefix-journal-') as temporary:
            for fault in ('none', 'after_journal_before_database', 'after_database_before_cache'):
                folder = Path(temporary) / fault
                store = SessionStore.create(folder, cfg, {'uuid': 'cpu-certificate-test'})
                if fault == 'after_journal_before_database':
                    with patch.object(store.gaps, 'apply', side_effect=OSError('injected committed journal/db interruption')):
                        try:
                            store.complete_exact_prefix(piece, certificate, oracle)
                        except OSError:
                            pass
                        else:
                            raise AssertionError('Fault was not exercised')
                elif fault == 'after_database_before_cache':
                    with patch.object(store, 'save', side_effect=OSError('injected cache interruption')):
                        try:
                            store.complete_exact_prefix(piece, certificate, oracle)
                        except OSError:
                            pass
                        else:
                            raise AssertionError('Fault was not exercised')
                else:
                    self.assertTrue(store.complete_exact_prefix(piece, certificate, oracle) == 10, 'store.complete_exact_prefix(piece, certificate, oracle) == 10')
                store.close()
                store = SessionStore.load(folder)
                self.assertTrue(store.meta['positions'] == 10 and store.meta['tests'] == 0, "store.meta['positions'] == 10 and store.meta['tests'] == 0")
                self.assertTrue(len(store.gaps) == 1 and store.gaps.get(prime) == upper, 'len(store.gaps) == 1 and store.gaps.get(prime) == upper')
                self.assertTrue(store.gaps.policy_count('count', prime + 10000) == 1, "store.gaps.policy_count('count', prime + 10000) == 1")
                before = (folder / 'session-events.jsonl').stat().st_size
                reject(lambda: store.complete_exact_prefix(piece, certificate, oracle))
                self.assertTrue((folder / 'session-events.jsonl').stat().st_size == before, "(folder / 'session-events.jsonl').stat().st_size == before")
                store.close()
