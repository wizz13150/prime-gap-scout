#pragma once
#include <stdint.h>
#include <math.h>
namespace whole68_retained_80 {
#include "backend/fast-batch-euler-v499.cuh"
}
#if defined(__CUDACC__)
#define WPT_HD __host__ __device__ __forceinline__
#else
#define WPT_HD inline
#endif
namespace whole68_port {
constexpr unsigned Bits=80,High=54210;
using State=whole68_retained_80::pgn_fast_batch499::State;
using ReferenceState=State;
static_assert(sizeof(State)==32,"Actual retained reciprocal/cache state, not State8");
WPT_HD bool referenceTest(uint64_t low,ReferenceState&state){using namespace whole68_retained_80;return pgn_fast_batch499::test<80,54210u>(low,High,state);}
WPT_HD bool test(uint64_t low,State&state){return referenceTest(low,state);}
}
#undef WPT_HD
