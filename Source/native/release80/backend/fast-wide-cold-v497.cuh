#pragma once
#include "fast-domains-u160.cuh"
#include "scaled173-78.cuh"
#ifdef __CUDACC__
#define PGN_COLD_HD __host__ __device__ __forceinline__
#define PGN_COLD_UNROLL _Pragma("unroll")
#else
#define PGN_COLD_HD inline
#define PGN_COLD_UNROLL
#endif
namespace pgn_fast_wide_cold497 {
using pgn_coach173::U96;using pgn_coach173::U128;
struct State{U96 u{};uint32_t u3=0;uint64_t low=0;float inverse=0;uint32_t high=0;};
static_assert(sizeof(State)==32,"Explicit upper quotient word uses former padding");
PGN_COLD_HD bool ge128(const U128&a,const U128&b){for(int i=3;i>=0;--i)if(a.w[i]!=b.w[i])return a.w[i]>b.w[i];return true;}
PGN_COLD_HD void sub128(U128&a,const U128&b){
#ifdef __CUDA_ARCH__
 uint32_t x,y,z,t;
 asm volatile("{.reg .u32 a0,a1,a2,a3;sub.cc.u32 a0,%4,%8;subc.cc.u32 a1,%5,%9;subc.cc.u32 a2,%6,%10;subc.u32 a3,%7,%11;mov.u32 %0,a0;mov.u32 %1,a1;mov.u32 %2,a2;mov.u32 %3,a3;}"
 :"=r"(x),"=r"(y),"=r"(z),"=r"(t):"r"(a.w[0]),"r"(a.w[1]),"r"(a.w[2]),"r"(a.w[3]),"r"(b.w[0]),"r"(b.w[1]),"r"(b.w[2]),"r"(b.w[3]));a=U128{{x,y,z,t}};
#else
 uint32_t c=0;for(unsigned i=0;i<4;++i){uint64_t t=uint64_t(a.w[i])-b.w[i]-c;a.w[i]=uint32_t(t);c=uint32_t(t>>63);}
#endif
}
PGN_COLD_HD unsigned add128(U128&a,const U128&b){uint64_t carry=0;PGN_COLD_UNROLL for(unsigned i=0;i<4;++i){uint64_t t=uint64_t(a.w[i])+b.w[i]+carry;a.w[i]=uint32_t(t);carry=t>>32;}return unsigned(carry);}
PGN_COLD_HD U128 shift128(const U128&a,unsigned bits){if(!bits)return a;return U128{{a.w[0]<<bits,(a.w[1]<<bits)|(a.w[0]>>(32-bits)),(a.w[2]<<bits)|(a.w[1]>>(32-bits)),(a.w[3]<<bits)|(a.w[2]>>(32-bits))}};}
PGN_COLD_HD U128 timesDigit(const U96&n,unsigned q){U128 out{};uint64_t carry=0;PGN_COLD_UNROLL for(unsigned i=0;i<3;++i){uint64_t t=uint64_t(n.w[i])*q+carry;out.w[i]=uint32_t(t);carry=t>>32;}out.w[3]=uint32_t(carry);return out;}
// The old digit hint used a fixed ~80-bit remainder window. Width-aware top
// words retain the same exact radix division without long corrective loops.
template<unsigned Bits>PGN_COLD_HD U96 reciprocal160(const U96&n,U96&r,float&inverse){
 static_assert(Bits>=79&&Bits<=95,"Shared batch domain");
 pgn_fast_domains::U192 rem{{0,0,0,0,0,1}};pgn_fast_domains::U96 q{},rawN{{n.w[0],n.w[1],n.w[2]}};
 const float denominator=float(n.w[2])*4294967296.0f+float(n.w[1])+float(n.w[0])*0x1p-32f;inverse=1.0f/denominator;
 PGN_COLD_UNROLL for(int k=5;k>=0;--k){
  const unsigned shift=unsigned(k)*16,topWord=(shift+Bits+15)/32,exponent=32*topWord-shift-32;
  const float highScale=exponent==64?18446744073709551616.0f:exponent==48?281474976710656.0f:4294967296.0f;
  const float lowScale=exponent==64?4294967296.0f:exponent==48?65536.0f:1.0f;
  const float estimate=(float(rem.w[topWord])*highScale+float(rem.w[topWord-1])*lowScale)*inverse;
  uint32_t digit=estimate>=65535.0f?65535u:estimate>0?uint32_t(estimate):0u;
  const auto unit=pgn_fast_domains::shifted(rawN,shift),product=pgn_fast_domains::timesDigit(unit,digit);
  int negative=-int(pgn_fast_domains::sub192(rem,product));
  while(negative<0){negative+=int(pgn_fast_domains::add192(rem,unit));--digit;}
  while(pgn_fast_domains::ge192(rem,unit)){pgn_fast_domains::sub192(rem,unit);++digit;}
  q.w[k/2]|=digit<<((k%2)*16);
 }
 r=U96{{rem.w[0],rem.w[1],rem.w[2]}};return U96{{q.w[0],q.w[1],q.w[2]}};
}
PGN_COLD_HD void lift(U128&u,U96&r,const U96&n,unsigned amount,float inverse){
 const U128 divisor{{n.w[0],n.w[1],n.w[2],0}},start{{r.w[0],r.w[1],r.w[2],0}};
 U128 a=shift128(start,amount);
 const float scaled=(float(a.w[3])*4294967296.0f+float(a.w[2]))*4294967296.0f+float(a.w[1]);
 const float estimate=scaled*inverse;const uint32_t limit=(1u<<amount)-1u;
 uint32_t digit=estimate>=float(limit)?limit:estimate>0?uint32_t(estimate):0u;
 const U128 product=timesDigit(n,digit);bool negative=!ge128(a,product);sub128(a,product);
 // Hints affect work only. Exact signed repair decides the quotient digit.
 while(negative){negative=add128(a,divisor)==0;--digit;}
 while(ge128(a,divisor)){sub128(a,divisor);++digit;}
 u=shift128(u,amount);u.w[0]|=digit;r=U96{{a.w[0],a.w[1],a.w[2]}};
}
template<unsigned Bits,unsigned K>PGN_COLD_HD U96 prepareCold(State&state,uint64_t low,uint32_t high){
 static_assert(K>=160&&K<=200,"Proved reciprocal fits128 bits");
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};U96 r{};float inverse=0;const U96 q=reciprocal160<Bits>(n,r,inverse);
 U128 u{{q.w[0],q.w[1],q.w[2],0}};
 PGN_COLD_UNROLL for(unsigned done=0;done<K-160;){const unsigned amount=K-160-done>16?16:K-160-done;lift(u,r,n,amount,inverse);done+=amount;}
 state.u=U96{{u.w[0],u.w[1],u.w[2]}};state.u3=u.w[3];state.low=low;state.high=high;state.inverse=inverse;return r;
}
}
#undef PGN_COLD_HD
#undef PGN_COLD_UNROLL
