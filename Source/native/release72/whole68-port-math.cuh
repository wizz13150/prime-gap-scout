#pragma once
#include <stdint.h>
#include <math.h>
namespace whole68_retained_72 {
#include "backend/fast70-73-family.cuh"
}
#if defined(__CUDACC__)
#define WPT_HD __host__ __device__ __forceinline__
#else
#define WPT_HD inline
#endif
namespace whole68_port {
constexpr unsigned Bits=72,High=162;
using State=whole68_retained_72::pgn_fast_domains_stateful::State;
using ReferenceState=State;
static_assert(sizeof(State)==32,"Actual retained reciprocal/cache state, not State8");
WPT_HD bool referenceTest(uint64_t low,ReferenceState&state){using namespace whole68_retained_72;return pgn_coach_fast7073::test<72>(low,High,state);}
WPT_HD bool test(uint64_t low,State&state){return referenceTest(low,state);}
}
#undef WPT_HD
