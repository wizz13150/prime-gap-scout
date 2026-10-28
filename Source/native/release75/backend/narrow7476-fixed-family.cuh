#pragma once
#include "fast-domains-stateful.cuh"
#include "fused-r160-groups-m365.cuh"
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
namespace pgn_narrow7476 {
using pgn_fast_domains::U96;
struct State {pgn_fast_domains_stateful::State core{};};
N7476_HD U96 local(U96 x){return x;}
template<unsigned Bits>N7476_HD U96 prepare(State&s,uint64_t low,uint32_t high){
 static_assert(Bits>=74&&Bits<=76,"Only proved finite family");
 return pgn_fast_domains_stateful::prepare(s.core,low,high);
}
N7476_HD U96 guardedSquare(U96 a,const U96&n,const U96&u){
 if(a.w[2]>=32768u)a=pgn_fast_domains::normalizeFinal12(a,n);
 return pgn_fast_domains::squareLazy(a,n,u);
}
N7476_HD U96 pair(U96 a,unsigned digit,const U96&n,const U96&u){
 a=guardedSquare(a,n,u);
 a=pgn_fast_domains::squareLazy(a,n,u);
 return pgn_fast_domains::shiftSmall(a,digit);
}
template<unsigned Bits>N7476_HD U96 residue(uint64_t low,uint32_t high,const U96&u,const U96&rem){
 static_assert(Bits>=74&&Bits<=76,"Only proved finite family");
 if constexpr(Bits==75){if(pgn_fused_r160_groups_m365::eligible<75>(high))return pgn_fused_r160_groups_m365::residue<75>(low,high,u,rem);}
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};
 U96 a=pgn_fast_domains::seedPrefix(n,u,rem,high>>(Bits-72));
 if constexpr(Bits==74)a=pair(a,high&3u,n,u);
 if constexpr(Bits==75){a=guardedSquare(a,n,u);if(high&4u)a=pgn_fast_domains::twice(a);a=pair(a,high&3u,n,u);}
 if constexpr(Bits==76){a=pair(a,(high>>2)&3u,n,u);a=pair(a,high&3u,n,u);}
 // No dynamic bit-count, high/low crossing, width choice or64bit extract.
 for(int at=31;at>=1;at-=2)a=pair(a,(n.w[1]>>(at-1))&3u,n,u);
 for(int at=31;at>=3;at-=2)a=pair(a,(n.w[0]>>(at-1))&3u,n,u);
 a=guardedSquare(a,n,u);if(low&2u)a=pgn_fast_domains::twice(a);
 return pgn_fast_domains::normalizeFinal12(a,n);
}
template<unsigned Bits>N7476_HD bool testWithParentState(uint64_t low,uint32_t high,pgn_fast_domains_stateful::State&core){
 if(!(low&1u)||high<(1u<<(Bits-65))||high>=(1u<<(Bits-64)))return false;
 const U96 rem=pgn_fast_domains_stateful::prepare(core,low,high),n{{uint32_t(low),uint32_t(low>>32),high}};
 const U96 r=residue<Bits>(low,high,core.u,rem);
 U96 expected{{1,0,0}};if(((low>>1)^(low>>2))&1u){expected=n;pgn_fast_domains::sub(expected,U96{{1,0,0}});}
 return r.w[0]==expected.w[0]&&r.w[1]==expected.w[1]&&r.w[2]==expected.w[2];
}
}
#undef N7476_HD
