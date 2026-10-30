#pragma once
#include <stdint.h>
#include <math.h>
namespace whole68_retained_71 {
#include "backend/r64mu71.cuh"
}
#if defined(__CUDACC__)
#define WPT_HD __host__ __device__ __forceinline__
#else
#define WPT_HD inline
#endif
namespace specialized_euler {
constexpr unsigned Bits = 71, High = 81;
using Value = whole68_retained_71::root71_mu::Value;
struct State {
    uint32_t bucketTag = 0, muLower = 0;
};
static_assert(sizeof(State) == 8, "Actual State8 scalar cache");
using ReferenceState = whole68_retained_71::root71_mu::State;
WPT_HD ReferenceState unpack(State s) {
    return ReferenceState{uint64_t(s.bucketTag) << 36, s.muLower, s.muLower ? 0x7136344du : 0u};
}
WPT_HD void pack(State &s, const ReferenceState &r) {
    s.bucketTag = uint32_t(r.anchor >> 36);
    s.muLower = r.mu;
}
WPT_HD bool referenceTest(uint64_t low, ReferenceState &state) {
    return whole68_retained_71::root71_mu::test(low, state);
}
WPT_HD bool test(uint64_t low, State &state) {
    auto s = unpack(state);
    const bool answer = referenceTest(low, s);
    pack(state, s);
    return answer;
}
} // namespace specialized_euler
#undef WPT_HD
