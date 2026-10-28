#pragma once
#include <stdint.h>
#include <math.h>
namespace whole68_retained_76 {
#include "backend/focused76-window1.cuh"
}
#if defined(__CUDACC__)
#define WPT_HD __host__ __device__ __forceinline__
#else
#define WPT_HD inline
#endif
namespace whole68_port {
constexpr unsigned Bits=76,High=2168;
using State=whole68_retained_76::pgn_fast_domains_stateful::State;
using ReferenceState=State;
static_assert(sizeof(State)==32,"Actual retained reciprocal/cache state, not State8");
WPT_HD bool referenceTest(uint64_t low,ReferenceState&state){using namespace whole68_retained_76;return pgn_focused76_w1::testWithParentState<76>(low,High,state);}
WPT_HD bool test(uint64_t low,State&state){return referenceTest(low,state);}
}
#undef WPT_HD
