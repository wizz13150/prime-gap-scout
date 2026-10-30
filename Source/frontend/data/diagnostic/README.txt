Public-reference Euler/Jacobi comparison
======================================
The fixed corpus contains274 odd68-bit integers. Expected decisions are
recomputed with independent Python integer pow before any device comparison.
Input, expected-output and device-source fingerprints are checked before use.
The predicate is base2 Euler/Jacobi, not the different exponentN-1 predicate.

The original public arithmetic excerpt retains its upstream attribution and
source commit. The comparison's paired kernels use identical inputs. Guards
and output values must agree before throughput is reported. NVRTC and its
matching builtins are loaded from the package for the Windows comparison.

This is a component diagnostic. Its test rate is not an end-to-end prime-gap
search rate and is not a claim of a world record or exhaustive interval coverage.
