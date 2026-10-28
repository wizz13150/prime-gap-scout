#pragma once
#include "scaled173-78.cuh"
#ifdef __CUDACC__
#define PGN_WIDE_HD __host__ __device__ __forceinline__
#define PGN_WIDE_UNROLL _Pragma("unroll")
#else
#define PGN_WIDE_HD inline
#define PGN_WIDE_UNROLL
#endif
// Arithmetic component only. Exact cold/cache/seed and full engine gates are
// mandatory before a caller may become a measured Fast candidate.
namespace pgn_fast_grouped_wide490 {
using pgn_coach173::U96;using pgn_coach173::U128;using pgn_coach173::U192;
struct Band160{uint32_t w[5];};
template<unsigned Word>PGN_WIDE_HD void addProduct(Band160&out,uint32_t a,uint32_t b){
 static_assert(Word<=3,"Product fits the five-word band");
 const uint64_t p=uint64_t(a)*b;
 uint64_t t=uint64_t(out.w[Word])+uint32_t(p);out.w[Word]=uint32_t(t);
 t=uint64_t(out.w[Word+1])+uint32_t(p>>32)+(t>>32);out.w[Word+1]=uint32_t(t);
 PGN_WIDE_UNROLL for(unsigned i=Word+2;i<5;++i){t=uint64_t(out.w[i])+(t>>32);out.w[i]=uint32_t(t);}
}
template<unsigned QuotientWords>PGN_WIDE_HD Band160 highBand(const U192&x,const U128&u){
 static_assert(QuotientWords==3||QuotientWords==4,"Exact reciprocal shape");
 const U96 low{{u.w[0],u.w[1],u.w[2]}};
 const U128 band=pgn_coach173::highBand9(x,low);
 Band160 out{{band.w[0],band.w[1],band.w[2],band.w[3],0}};
 if constexpr(QuotientWords==4){
  // The omitted low two input words contribute a fraction strictly below u3.
  addProduct<0>(out,x.w[2],u.w[3]);addProduct<1>(out,x.w[3],u.w[3]);
  addProduct<2>(out,x.w[4],u.w[3]);addProduct<3>(out,x.w[5],u.w[3]);
 }
 return out;
}
template<unsigned K>PGN_WIDE_HD U96 quotientLow96(const Band160&b){
 static_assert(K>=160&&K<=223,"Proved extraction window");
 constexpr unsigned Word=(K-160)/32,Part=(K-160)%32;
 if constexpr(Part==0)return U96{{b.w[Word],b.w[Word+1],b.w[Word+2]}};
 else return U96{{(b.w[Word]>>Part)|(b.w[Word+1]<<(32-Part)),
  (b.w[Word+1]>>Part)|(b.w[Word+2]<<(32-Part)),
  (b.w[Word+2]>>Part)|(b.w[Word+3]<<(32-Part))}};
}
PGN_WIDE_HD U128 shift128(const U128&u,unsigned digit){
#ifdef __CUDA_ARCH__
 U128 out{};
 asm volatile("{.reg .u32 t0,t1,t2,t3;shl.b32 t0,%4,%8;shf.l.wrap.b32 t1,%4,%5,%8;shf.l.wrap.b32 t2,%5,%6,%8;shf.l.wrap.b32 t3,%6,%7,%8;mov.u32 %0,t0;mov.u32 %1,t1;mov.u32 %2,t2;mov.u32 %3,t3;}"
  :"=r"(out.w[0]),"=r"(out.w[1]),"=r"(out.w[2]),"=r"(out.w[3])
  :"r"(u.w[0]),"r"(u.w[1]),"r"(u.w[2]),"r"(u.w[3]),"r"(digit));return out;
#else
 if(!digit)return u;
 return U128{{u.w[0]<<digit,(u.w[1]<<digit)|(u.w[0]>>(32-digit)),
  (u.w[2]<<digit)|(u.w[1]>>(32-digit)),(u.w[3]<<digit)|(u.w[2]>>(32-digit))}};
#endif
}
PGN_WIDE_HD U96 shiftLow96(const U192&x,unsigned digit){
#ifdef __CUDA_ARCH__
 U96 out{};
 asm volatile("{.reg .u32 t0,t1,t2;shl.b32 t0,%3,%6;shf.l.wrap.b32 t1,%3,%4,%6;shf.l.wrap.b32 t2,%4,%5,%6;mov.u32 %0,t0;mov.u32 %1,t1;mov.u32 %2,t2;}"
  :"=r"(out.w[0]),"=r"(out.w[1]),"=r"(out.w[2])
  :"r"(x.w[0]),"r"(x.w[1]),"r"(x.w[2]),"r"(digit));return out;
#else
 if(!digit)return U96{{x.w[0],x.w[1],x.w[2]}};
 return U96{{x.w[0]<<digit,(x.w[1]<<digit)|(x.w[0]>>(32-digit)),(x.w[2]<<digit)|(x.w[1]>>(32-digit))}};
#endif
}
template<unsigned Bits,unsigned K,unsigned QuotientWords>PGN_WIDE_HD U96 square(const U96&a,unsigned digit,const U96&n,const U128&u){
 static_assert(Bits>=79&&Bits<=95,"Batch model domain");
 U192 x{};
 if constexpr(Bits==79)x=pgn_coach173::square5Known(a);else x=pgn_coach173::square6(a);
 const U128 v=shift128(u,digit);const auto q=quotientLow96<K>(highBand<QuotientWords>(x,v));
 U96 out=shiftLow96(x,digit);pgn_coach173::sub(out,pgn_coach173::productLow96(q,n));return out;
}
}
#undef PGN_WIDE_HD
#undef PGN_WIDE_UNROLL
