#pragma once
#include <stdint.h>
#include <math.h>
#if defined(__CUDACC__)
#define PGN_RETAINED_HD __host__ __device__ __forceinline__
#else
#define PGN_RETAINED_HD inline
#endif
// Per-family namespaces preserve original header bodies and isolate identical filenames.
namespace pgn_release_backend69 {
namespace impl {
#include "arithmetic/bits_69/prime_test.cuh"
}
using State = impl::pgn_fast_domains_stateful::State;
static_assert(sizeof(State) == 32, "Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::pgn_fast69::test(low, 21u, state);
}
} // namespace pgn_release_backend69
namespace pgn_release_backend70 {
namespace impl {
#include "arithmetic/bits_70/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Exact retained point State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend70
namespace pgn_release_backend71 {
namespace impl {
#include "arithmetic/bits_71/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Exact retained point State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend71
namespace pgn_release_backend72 {
namespace impl {
#include "arithmetic/bits_72/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend72
namespace pgn_release_backend73 {
namespace impl {
#include "arithmetic/bits_73/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend73
namespace pgn_release_backend74 {
namespace impl {
#include "arithmetic/bits_74/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend74
namespace pgn_release_backend75 {
namespace impl {
#include "arithmetic/bits_75/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend75
namespace pgn_release_backend76 {
namespace impl {
#include "arithmetic/bits_76/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend76
namespace pgn_release_backend77 {
namespace impl {
#include "arithmetic/bits_77/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend77
namespace pgn_release_backend78 {
namespace impl {
#include "arithmetic/bits_78/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Exact retained point State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend78
namespace pgn_release_backend79 {
namespace impl {
#include "arithmetic/bits_79/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Exact retained point State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend79
namespace pgn_release_backend80 {
namespace impl {
#include "arithmetic/bits_80/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend80
namespace pgn_release_backend81 {
namespace impl {
#include "arithmetic/bits_81/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend81
namespace pgn_release_backend82 {
namespace impl {
#include "arithmetic/bits_82/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend82
namespace pgn_release_backend83 {
namespace impl {
#include "arithmetic/bits_83/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend83
namespace pgn_release_backend84 {
namespace impl {
#include "arithmetic/bits_84/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend84
namespace pgn_release_backend85 {
namespace impl {
#include "arithmetic/bits_85/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend85
namespace pgn_release_backend86 {
namespace impl {
#include "arithmetic/bits_86/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend86
namespace pgn_release_backend87 {
namespace impl {
#include "arithmetic/bits_87/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend87
namespace pgn_release_backend88 {
namespace impl {
#include "arithmetic/bits_88/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend88
namespace pgn_release_backend89 {
namespace impl {
#include "arithmetic/bits_89/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend89
namespace pgn_release_backend90 {
namespace impl {
#include "arithmetic/bits_90/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend90
namespace pgn_release_backend91 {
namespace impl {
#include "arithmetic/bits_91/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend91
namespace pgn_release_backend92 {
namespace impl {
#include "arithmetic/bits_92/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend92
namespace pgn_release_backend93 {
namespace impl {
#include "arithmetic/bits_93/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend93
namespace pgn_release_backend94 {
namespace impl {
#include "arithmetic/bits_94/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend94
namespace pgn_release_backend95 {
namespace impl {
#include "arithmetic/bits_95/prime_test.cuh"
}
using State = impl::specialized_euler::State;
static_assert(sizeof(State) == 8, "Selected optimized State8");
PGN_RETAINED_HD bool test(uint64_t low, State &state) {
    return impl::specialized_euler::test(low, state);
}
} // namespace pgn_release_backend95
#undef PGN_RETAINED_HD
