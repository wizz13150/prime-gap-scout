#pragma once
#include "fast-domains-stateful.cuh"
#include "fused-r160-groups-m378.cuh"
#ifdef __CUDACC__
#define N7476_HD __host__ __device__ __forceinline__
#else
#define N7476_HD inline
#endif
// Exact retained R160/three-word reciprocal, five-word square and32B cache.
// Before every square, a<2^79, hence X<2^158. The retained high-band estimator
// misses less than4+X/2^160<4.25 quotient units: integer deficit<=4, r<5N.
// W2 shifts produce a<40N. H>=512 implies the original final normalizer's
// q=floor(a.high/(H+1)) needs at most two exact subtractions.
// R160's two64bit column sums are bounded below2^64 when X<2^158.
// A square output r<5N<2^79 through76 needs no second guard.
namespace pgn_focused76_w1 {
using pgn_fast_domains::U96;using pgn_fast_domains::ge;using pgn_fast_domains::sub;
N7476_HD U96 normalizeReusedHint(U96 a,const U96&n,float inverse){
 const float estimate=(float(a.w[2])*4294967296.0f+float(a.w[1]))*inverse;
 const uint32_t quotient=estimate>=32768.0f?32768u:estimate>0?uint32_t(estimate):0u;
 uint64_t product=uint64_t(n.w[0])*quotient;U96 multiple{{uint32_t(product),0,0}};
 product=uint64_t(n.w[1])*quotient+(product>>32);multiple.w[1]=uint32_t(product);multiple.w[2]=n.w[2]*quotient+uint32_t(product>>32);
 int sign=-int(sub(a,multiple));
 while(sign<0){uint64_t carry=0;for(int i=0;i<3;++i){uint64_t value=uint64_t(a.w[i])+n.w[i]+carry;a.w[i]=uint32_t(value);carry=value>>32;}sign+=int(carry);}
 while(ge(a,n))sub(a,n);
 return a;
}

struct State {pgn_fast_domains_stateful::State core{};};
N7476_HD U96 local(U96 x){return x;}
template<unsigned Bits>N7476_HD U96 prepare(State&s,uint64_t low,uint32_t high){
 static_assert(Bits>=74&&Bits<=76,"Only proved finite family");
 return pgn_fast_domains_stateful::prepare(s.core,low,high);
}
N7476_HD U96 guardedSquare(U96 a,const U96&n,const U96&u,float inverse){
 if(a.w[2]>=32768u)a=normalizeReusedHint(a,n,inverse);
 return pgn_fast_domains::squareLazy(a,n,u);
}
N7476_HD U96 pair(U96 a,unsigned digit,const U96&n,const U96&u,float inverse){
 a=guardedSquare(a,n,u,inverse);
 a=pgn_fast_domains::squareLazy(a,n,u);
 return pgn_fast_domains::shiftSmall(a,digit);
}
// Fixed high2168 only. Each R160 square gives r<5N; the next
// input is at most twice r, hence a<10N<2^79. No window guard or
// hint normalization is needed inside this W1 schedule.
template<unsigned Bits>N7476_HD U96 residue(uint64_t low,uint32_t high,const U96&u,const U96&rem,float inverse){
 static_assert(Bits==76,"Fixed76 W1 only");
 if(high==2168u)return pgn_fused_r160_groups_m378::residue<76>(low,high,u,rem);
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};
 U96 a=pgn_fast_domains::seedPrefix(n,u,rem,high>>4);
 for(int at=3;at>=0;--at){a=pgn_fast_domains::squareLazy(a,n,u);if((high>>at)&1u)a=pgn_fast_domains::twice(a);}
 for(int at=31;at>=0;--at){a=pgn_fast_domains::squareLazy(a,n,u);if((n.w[1]>>at)&1u)a=pgn_fast_domains::twice(a);}
 for(int at=31;at>=1;--at){a=pgn_fast_domains::squareLazy(a,n,u);if((n.w[0]>>at)&1u)a=pgn_fast_domains::twice(a);}
 return pgn_fast_domains::normalizeFinal12(a,n);
}
template<unsigned Bits>N7476_HD bool testWithParentState(uint64_t low,uint32_t high,pgn_fast_domains_stateful::State&core){
 if(!(low&1u)||high!=2168u)return false;
 const U96 rem=pgn_fast_domains_stateful::prepare(core,low,high),n{{uint32_t(low),uint32_t(low>>32),high}};
 const U96 r=residue<Bits>(low,high,core.u,rem,core.inverse);
 U96 expected{{1,0,0}};if(((low>>1)^(low>>2))&1u){expected=n;pgn_fast_domains::sub(expected,U96{{1,0,0}});}
 return r.w[0]==expected.w[0]&&r.w[1]==expected.w[1]&&r.w[2]==expected.w[2];
}
}
#undef N7476_HD
