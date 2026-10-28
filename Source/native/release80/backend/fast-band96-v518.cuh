#pragma once
#include "scaled173-78.cuh"
#ifdef __CUDACC__
#define PGN_B96_HD __host__ __device__ __forceinline__
#else
#define PGN_B96_HD inline
#endif
namespace pgn_fast_band96_518 {
// For the separate 80..82 lazy engines: a<4N, K=2Bits+5 and
// U<2^(K-Bits+1) imply a^2*U/2^160 < 2^(3Bits-150) <=2^96.
// Every term is positive; discarding carry above word2 is therefore exact.
PGN_B96_HD pgn_coach173::U96 highBand(const pgn_coach173::U192&x,const pgn_coach173::U96&u){
#ifdef __CUDA_ARCH__
 pgn_coach173::U96 out{};
 asm volatile("{\n\t.reg .u32 a0,a1,a2,t;\n\t"
  "mul.hi.u32 a0,%5,%7;\n\t"
  "mul.hi.u32 t,%3,%9;\n\t"
  "add.cc.u32 a0,a0,t;\n\taddc.u32 a1,0,0;\n\t"
  "mul.hi.u32 t,%4,%8;\n\t"
  "add.cc.u32 a0,a0,t;\n\taddc.u32 a1,a1,0;\n\t"
  "mov.u32 a2,0;\n\t"
  "mad.lo.cc.u32 a0,%4,%9,a0;\n\tmadc.hi.cc.u32 a1,%4,%9,a1;\n\taddc.u32 a2,a2,0;\n\t"
  "mad.lo.cc.u32 a0,%5,%8,a0;\n\tmadc.hi.cc.u32 a1,%5,%8,a1;\n\taddc.u32 a2,a2,0;\n\t"
  "mad.lo.cc.u32 a0,%6,%7,a0;\n\tmadc.hi.cc.u32 a1,%6,%7,a1;\n\taddc.u32 a2,a2,0;\n\t"
  "mad.lo.cc.u32 a1,%5,%9,a1;\n\tmadc.hi.u32 a2,%5,%9,a2;\n\t"
  "mad.lo.cc.u32 a1,%6,%8,a1;\n\tmadc.hi.u32 a2,%6,%8,a2;\n\t"
  "mad.lo.u32 a2,%6,%9,a2;\n\t"
  "mov.u32 %0,a0;\n\tmov.u32 %1,a1;\n\tmov.u32 %2,a2;\n\t}"
  :"=r"(out.w[0]),"=r"(out.w[1]),"=r"(out.w[2])
  :"r"(x.w[2]),"r"(x.w[3]),"r"(x.w[4]),"r"(x.w[5]),"r"(u.w[0]),"r"(u.w[1]),"r"(u.w[2]));return out;
#else
 const auto b=pgn_coach173::highBand9(x,u);return pgn_coach173::U96{{b.w[0],b.w[1],b.w[2]}};
#endif
}
}
#undef PGN_B96_HD
