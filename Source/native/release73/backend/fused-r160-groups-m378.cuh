#pragma once
#include "fast-domains-stateful.cuh"
#include "M315-final-one.cuh"
#ifdef __CUDACC__
#define F160_HD __host__ __device__ __forceinline__
#else
#define F160_HD inline
#endif
// Component SOURCE, not wired into a retained miner. No speed qualification.
// mu=floor(2^160/N). Only the explicit eligible profiles below are proved.
// For X=A^2 and V=mu<<digit, omitted high-band deficit D<6 gives
// 0<=r/N<6+(A/N)^2*2^digit*N^2/2^160. Whole-group induction keeps A<12N;
// each square fits five words, V fits96 and both quotient columns fit64.
// Exact rational profile/column bounds: model.actual.json, SHA00567293...851D2.
// No change to R160 seed/cache or final two-repair normalizer.
// Caller MUST retain its original exact fallback outside eligible(); this
// header supplies fallback-taking entry points, never a silent false reject.
namespace pgn_fused_r160_groups_m378 {
using pgn_fast_domains::U96;
struct Words5 {uint32_t w[5];};
F160_HD Words5 square5(const U96&a){
#ifdef __CUDA_ARCH__
 uint32_t a0,a1,a2,a3,a4;
 // C = a0*a1 + B*a0*a2 + B^2*a1*a2, B=2^32.
 // Form 2*C once, then add the three diagonal products in one carry chain.
 // All five output limbs are exact for input<2^80 (in particular a<12*n).
 // No 64-bit column sums, branch or floating approximation is introduced.
 asm volatile("{\n\t"
  ".reg .u64 p00,p01,p02,p11,p12;\n\t"
  ".reg .u32 l00,h00,l01,h01,l02,h02,l11,h11,l12,h12,z;\n\t"
  ".reg .u32 c2,c3,c4,d1,d2,d3,d4,r1,r2,r3,r4;\n\t"
  "mul.wide.u32 p00,%5,%5;\n\tmul.wide.u32 p01,%5,%6;\n\t"
  "mul.wide.u32 p02,%5,%7;\n\tmul.wide.u32 p11,%6,%6;\n\t"
  "mul.wide.u32 p12,%6,%7;\n\tmul.lo.u32 z,%7,%7;\n\t"
  "mov.b64 {l00,h00},p00;\n\tmov.b64 {l01,h01},p01;\n\t"
  "mov.b64 {l02,h02},p02;\n\tmov.b64 {l11,h11},p11;\n\t"
  "mov.b64 {l12,h12},p12;\n\t"
  "add.cc.u32 c2,h01,l02;\n\taddc.cc.u32 c3,h02,l12;\n\taddc.u32 c4,h12,0;\n\t"
  "shl.b32 d1,l01,1;\n\tshf.l.wrap.b32 d2,l01,c2,1;\n\t"
  "shf.l.wrap.b32 d3,c2,c3,1;\n\tshf.l.wrap.b32 d4,c3,c4,1;\n\t"
  "add.cc.u32 r1,d1,h00;\n\taddc.cc.u32 r2,d2,l11;\n\t"
  "addc.cc.u32 r3,d3,h11;\n\taddc.u32 r4,d4,z;\n\t"
  "mov.u32 %0,l00;\n\tmov.u32 %1,r1;\n\tmov.u32 %2,r2;\n\t"
  "mov.u32 %3,r3;\n\tmov.u32 %4,r4;\n\t}"
  :"=r"(a0),"=r"(a1),"=r"(a2),"=r"(a3),"=r"(a4)
  :"r"(a.w[0]),"r"(a.w[1]),"r"(a.w[2]));
#else
 const uint64_t p00=uint64_t(a.w[0])*a.w[0],p01=uint64_t(a.w[0])*a.w[1];
 const uint64_t p02=uint64_t(a.w[0])*a.w[2],p11=uint64_t(a.w[1])*a.w[1];
 const uint64_t p12=uint64_t(a.w[1])*a.w[2],p22=uint64_t(a.w[2])*a.w[2];
 const uint32_t a0=uint32_t(p00);uint64_t s=(p00>>32)+2ULL*uint32_t(p01);const uint32_t a1=uint32_t(s);
 s=(s>>32)+2ULL*(p01>>32)+2ULL*uint32_t(p02)+uint32_t(p11);const uint32_t a2=uint32_t(s);
 s=(s>>32)+2ULL*(p02>>32)+(p11>>32)+2ULL*uint32_t(p12);const uint32_t a3=uint32_t(s);
 s=(s>>32)+2ULL*(p12>>32)+p22;const uint32_t a4=uint32_t(s);
#endif
 return Words5{{a0,a1,a2,a3,a4}};
}
template<unsigned Bits>F160_HD bool eligible(uint32_t high){
 static_assert(Bits>=72&&Bits<=77,"Only proved profiles72..77");
 if constexpr(Bits==72)return high>=129u&&high<=255u;
 if constexpr(Bits==73)return high>=256u&&high<=511u;
 if constexpr(Bits==74)return high>=512u&&high<=1023u;
 if constexpr(Bits==75)return high>=1024u&&high<=2047u;
 if constexpr(Bits==76)return high>=2048u&&high<=2303u;
 if constexpr(Bits==77)return high>=4096u&&high<=5439u;
 return false;
}
template<bool Fused>F160_HD U96 step(const U96&a,unsigned digit,const U96&n,const U96&u){
 const Words5 x=square5(a);
 if constexpr(!Fused)return pgn_fast_domains::reduceSquaredWords(x.w[0],x.w[1],x.w[2],x.w[3],x.w[4],n,u);
 const U96 v=pgn_fast_domains::shiftSmall(u,digit);
 const uint64_t h=uint64_t(pgn_fast_domains::high32(x.w[4],v.w[0]))+pgn_fast_domains::high32(x.w[2],v.w[2])+pgn_fast_domains::high32(x.w[3],v.w[1]);
 const uint64_t s3=pgn_fast_domains::fusedWide(x.w[4],v.w[1],pgn_fast_domains::fusedWide(x.w[3],v.w[2],h));
 const uint64_t s4=pgn_fast_domains::fusedWide(x.w[4],v.w[2],s3>>32);
 const uint32_t q0=uint32_t(s3),q1=uint32_t(s4),q2=uint32_t(s4>>32);
 const uint64_t p0=pgn_fast_domains::fusedWide(q0,n.w[0],0);
 const uint64_t p12=pgn_fast_domains::fusedWide(q1,n.w[0],pgn_fast_domains::fusedWide(q0,n.w[1],p0>>32));
 const uint32_t p2=uint32_t(p12>>32)+q0*n.w[2]+q1*n.w[1]+q2*n.w[0];
 U96 r=pgn_fast_domains::shiftSmall(U96{{x.w[0],x.w[1],x.w[2]}},digit);
 pgn_fast_domains::sub(r,U96{{uint32_t(p0),uint32_t(p12),p2}});return r;
}
template<unsigned Width>F160_HD U96 group(U96 a,unsigned digit,const U96&n,const U96&u){
 static_assert(Width>=1&&Width<=3,"Closed group1..3");
 if constexpr(Width>=3)a=step<false>(a,0,n,u);
 if constexpr(Width>=2)a=step<false>(a,0,n,u);
 return step<true>(a,digit,n,u);
}
// Precondition eligible<Bits>(high), low odd, exact parent quotient/remainder.
template<unsigned Bits>F160_HD U96 residue(uint64_t low,uint32_t high,const U96&u,const U96&rem){
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};
 U96 a=pgn_fast_domains::seedPrefix(n,u,rem,high>>(Bits-72));
 if constexpr(Bits==72){
 for(int shift=29;shift>=2;shift-=3) a=group<3>(a,(n.w[1]>>shift)&7u,n,u);
 a=group<3>(a,((n.w[0]>>31)|(n.w[1]<<1))&7u,n,u);
 for(int shift=28;shift>=1;shift-=3) a=group<3>(a,(n.w[0]>>shift)&7u,n,u);
 }
 if constexpr(Bits==73){
 a=group<3>(a,((n.w[1]>>30)|(n.w[2]<<2))&7u,n,u);
 for(int shift=27;shift>=0;shift-=3) a=group<3>(a,(n.w[1]>>shift)&7u,n,u);
 for(int shift=29;shift>=2;shift-=3) a=group<3>(a,(n.w[0]>>shift)&7u,n,u);
 a=group<1>(a,(n.w[0]>>1)&1u,n,u);
 }
 if constexpr(Bits==74){
 a=group<3>(a,((n.w[1]>>31)|(n.w[2]<<1))&7u,n,u);
 for(int shift=28;shift>=1;shift-=3) a=group<3>(a,(n.w[1]>>shift)&7u,n,u);
 a=group<3>(a,((n.w[0]>>30)|(n.w[1]<<2))&7u,n,u);
 for(int shift=27;shift>=3;shift-=3) a=group<3>(a,(n.w[0]>>shift)&7u,n,u);
 a=group<2>(a,(n.w[0]>>1)&3u,n,u);
 }
 if constexpr(Bits==75){
 a=group<3>(a,(n.w[2]>>0)&7u,n,u);
 for(int shift=29;shift>=2;shift-=3) a=group<3>(a,(n.w[1]>>shift)&7u,n,u);
 a=group<3>(a,((n.w[0]>>31)|(n.w[1]<<1))&7u,n,u);
 for(int shift=28;shift>=1;shift-=3) a=group<3>(a,(n.w[0]>>shift)&7u,n,u);
 }
 if constexpr(Bits==76){
 a=group<3>(a,(n.w[2]>>1)&7u,n,u);
 a=group<3>(a,((n.w[1]>>30)|(n.w[2]<<2))&7u,n,u);
 for(int shift=27;shift>=0;shift-=3) a=group<3>(a,(n.w[1]>>shift)&7u,n,u);
 for(int shift=29;shift>=2;shift-=3) a=group<3>(a,(n.w[0]>>shift)&7u,n,u);
 a=group<1>(a,(n.w[0]>>1)&1u,n,u);
 }
 if constexpr(Bits==77){
 for(int shift=3;shift>=1;shift-=2) a=group<2>(a,(n.w[2]>>shift)&3u,n,u);
 a=group<2>(a,((n.w[1]>>31)|(n.w[2]<<1))&3u,n,u);
 for(int shift=29;shift>=1;shift-=2) a=group<2>(a,(n.w[1]>>shift)&3u,n,u);
 a=group<2>(a,((n.w[0]>>31)|(n.w[1]<<1))&3u,n,u);
 for(int shift=29;shift>=1;shift-=2) a=group<2>(a,(n.w[0]>>shift)&3u,n,u);
 }
 return pgn_root315::normalizeFinalOne(a,n);
}
template<unsigned Bits,class Fallback>F160_HD U96 residueWithFallback(uint64_t low,uint32_t high,const U96&u,const U96&rem,Fallback fallback){
 if(!eligible<Bits>(high))return fallback(low,high,u,rem);
 return residue<Bits>(low,high,u,rem);
}
template<unsigned Bits,class Fallback>F160_HD bool testWithFallback(uint64_t low,uint32_t high,pgn_fast_domains_stateful::State&state,Fallback fallback){
 if(!eligible<Bits>(high))return fallback(low,high,state);
 if(!(low&1u))return false;
 const U96 rem=pgn_fast_domains_stateful::prepare(state,low,high);
 const U96 r=residue<Bits>(low,high,state.u,rem),n{{uint32_t(low),uint32_t(low>>32),high}};
 U96 expected{{1u,0u,0u}};
 if(((low>>1)^(low>>2))&1u){expected=n;pgn_fast_domains::sub(expected,U96{{1u,0u,0u}});}
 return r.w[0]==expected.w[0]&&r.w[1]==expected.w[1]&&r.w[2]==expected.w[2];
}
}
#undef F160_HD
