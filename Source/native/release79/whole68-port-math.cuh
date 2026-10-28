#pragma once
#include <stdint.h>
#include <math.h>
#include "mu128-coeff-state8.cuh"
namespace whole68_retained_79 {
#include "backend/mapped79-repaired.cuh"
}
#ifdef __CUDACC__
#define B8K_HD __host__ __device__ __forceinline__
#else
#define B8K_HD inline
#endif
namespace whole68_port {
constexpr unsigned Bits=79,High=21684,CoeffBits=166;
using State=whole68_mu128::State;using Context=whole68_mu128_coeff::Context;
using ReferenceState=whole68_retained_79::pgn_mapped79::State;
using RawState=whole68_retained_79::pgn_mapped79::State;
using Value=whole68_retained_79::pgn_coach173::U96;
static_assert(sizeof(State)==8,"Certified M128 persists; current coefficient is temporary");
B8K_HD Context referencePrepare(uint64_t low,RawState&raw){const auto r=whole68_retained_79::pgn_mapped79::prepare<79>(raw,low,High);const auto&u=raw.core.u;
 Context ctx;for(unsigned j=0;j<3;++j){ctx.quotient.w[j]=u.w[j];ctx.remainder.w[j]=r.w[j];}return ctx;}
B8K_HD bool prepare(uint64_t low,State&state,Context&ctx){if(whole68_mu128_coeff::prepareWarm<High,CoeffBits>(low,state,ctx))return true;RawState cold{};ctx=referencePrepare(low,cold);whole68_mu128_coeff::acceptCold<CoeffBits>(state,ctx);return false;}
B8K_HD bool evaluate(uint64_t low,const Context&ctx){const Value u{{ctx.quotient.w[0],ctx.quotient.w[1],ctx.quotient.w[2]}},rem{{ctx.remainder.w[0],ctx.remainder.w[1],ctx.remainder.w[2]}};
 const auto r=whole68_retained_79::pgn_mapped79::residue<Bits>(low,High,u,rem);Value expected{{1,0,0}},n{{uint32_t(low),uint32_t(low>>32),High}};if(((low>>1)^(low>>2))&1u){expected=n;whole68_retained_79::pgn_coach173::sub(expected,Value{{1,0,0}});}return r.w[0]==expected.w[0]&&r.w[1]==expected.w[1]&&r.w[2]==expected.w[2];}
B8K_HD bool test(uint64_t low,State&state){if(!(low&1))return false;Context ctx;prepare(low,state,ctx);return evaluate(low,ctx);}
B8K_HD bool referenceTest(uint64_t low,ReferenceState&state){using namespace whole68_retained_79;return pgn_mapped79::test<79>(low,High,state);}
}
#undef B8K_HD
