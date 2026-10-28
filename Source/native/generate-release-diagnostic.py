"""Reproduce the diagnostic corpus from frozen inputs and independent integer pow.

The --metadata-only mode only repackages already independently computed CPU golds;
it does not execute an oracle, compiler, CUDA, a driver, or a subprocess. Root must
run the default mode under its own bounded CPU allocation before qualification.
"""
from pathlib import Path
import argparse, hashlib, json, struct, zipfile

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
ARCHIVE = WORKSPACE / 'output/reports/FERMAT-Perig-vs-PGN-20261025.zip'
PREFIX = 'FERMAT-Perig-vs-PGN-20261025/'
PUBLIC_COMMIT = '9d41f2709666d240c073439c37722c6ff6cb5b44'

def generate(metadata_only=False):
    with zipfile.ZipFile(ARCHIVE) as archive:
        raw_lows = archive.read(PREFIX + 'data/lows.bin')
        raw_expected = archive.read(PREFIX + 'data/expected-euler-jacobi.bin')
        public = archive.read(PREFIX + 'original/perig-public-excerpt.cuh').decode('utf-8').replace('\r\n','\n')
    lows = struct.unpack('<' + 'Q' * (len(raw_lows)//8), raw_lows)
    expected = struct.unpack('<' + 'I' * (len(raw_expected)//4), raw_expected)
    assert len(lows) == len(expected) == 274 and all(low & 1 for low in lows)
    assert set(expected) == {0,1}
    if not metadata_only:
        independently_computed = []
        for low in lows:
            n = (10 << 64) + low
            residue = pow(2, n >> 1, n)
            wanted = n-1 if ((low>>1) ^ (low>>2)) & 1 else 1
            independently_computed.append(int(residue == wanted))
        assert tuple(independently_computed) == expected
    # Device-only packaging: no integer operation or exponent bit is changed.
    device_public = public.replace('__host__ __device__', '__device__')
    assert device_public.replace('__device__', '__host__ __device__') == public
    entries = '\n'.join('    ' + ', '.join(f'0x{x:016x}ULL' for x in lows[i:i+4]) + ',' for i in range(0,len(lows),4))
    truths = '\n'.join('    ' + ', '.join(str(x)+'u' for x in expected[i:i+16]) + ',' for i in range(0,len(expected),16))
    text = '''#pragma once
// Generated from frozen inputs. Re-run generate-release-diagnostic.py for an
// independent Python-integer oracle. Runtime also recomputes an independent
// portable CPU oracle; the GPU never generates expected values.
#include <cstdint>
namespace pgn_release_diag {
constexpr unsigned InputCount = 274;
constexpr const char* PublicCommit = "''' + PUBLIC_COMMIT + '''";
constexpr const char* Predicate = "Euler/Jacobi base 2: 2^(N>>1) mod N = Jacobi(2,N)";
constexpr uint64_t Inputs[InputCount] = {
''' + entries + '''
};
constexpr uint32_t IndependentCpuGold[InputCount] = {
''' + truths + '''
};
}
#if PGN_RELEASE_ENABLE_PUBLIC_PERIG && defined(__CUDA_ARCH__)
namespace pgn_release_perig_public {
typedef unsigned __int128 uint128_t;
''' + device_public + '''
}
#endif
'''
    target = HERE / 'diagnostic_data.h'
    target.write_text(text, encoding='utf-8', newline='\n')
    manifest = {
        'schema':'PGN68_RELEASE_DIAGNOSTIC_SOURCE_DATA_V1',
        'inputs':274, 'high_word':10, 'predicate':'Euler/Jacobi base 2, not Fermat N-1',
        'public_commit':PUBLIC_COMMIT,
        'public_excerpt_sha256':hashlib.sha256(public.encode()).hexdigest().upper(),
        'device_reference_packaging':'Only __host__ qualifier removed; device integer operations and exponent loop byte-exact',
        'input_sha256':hashlib.sha256(raw_lows).hexdigest().upper(),
        'expected_cpu_sha256':hashlib.sha256(raw_expected).hexdigest().upper(),
        'fresh_python_pow_executed':not metadata_only,
        'runtime_independent_cpu_oracle_also_required':True,
        'header_sha256':hashlib.sha256(target.read_bytes()).hexdigest().upper(),
        'compiler':False, 'Driver':False, 'GPU':False,
    }
    (HERE/'diagnostic-data-source.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata-only',action='store_true')
    args=parser.parse_args()
    generate(args.metadata_only)
