#pragma once
#include "fast-domains-stateful.cuh"
#include "M315-final-one.cuh"
#include "fused-r160-groups-m378.cuh"
#ifdef __CUDACC__
#define F7073_HD __host__ __device__ __forceinline__
#else
#define F7073_HD inline
#endif
// Common exact family, not a claim of throughput parity. U160/reducer/seed/cache
// are inherited verbatim from pinned warm261 parent. W3 at70, W2 at71..73:
// r<6n -> W2shift<48n<2^79 at73; square fits five limbs. Unchecked W3 cloning
// beyond70 would exceed the parent's a<768n<2^80 guarantee.
namespace pgn_coach_fast7073 {
using pgn_fast_domains::U96;
F7073_HD U96 pair(U96 a,unsigned digit,const U96&n,const U96&u){a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);return pgn_fast_domains::shiftSmall(a,digit);}
template<unsigned Bits>F7073_HD U96 residue(uint64_t low,uint32_t high,const U96&u,const U96&rem){
 if constexpr(Bits==73)if(high==325u)return pgn_fused_r160_groups_m378::residue<73>(low,325u,u,rem);

 static_assert(Bits>=70&&Bits<=73,"Admitted family only");
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};constexpr unsigned hb=Bits-64;
 unsigned prefix;if constexpr(hb<8)prefix=(high<<(8-hb))|unsigned(low>>(56+hb));else prefix=high>>(hb-8);
 U96 a=pgn_fast_domains::seedPrefix(n,u,rem,prefix);
 if constexpr(Bits==70){
  // Preserve the already CPU-validated V25570 source operation order.
  for(int at=29;at>=2;at-=3){a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::shiftSmall(a,(n.w[1]>>(at-2))&7u);}
  for(int at=31;at>=4;at-=3){a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::shiftSmall(a,(n.w[0]>>(at-2))&7u);}
  a=pgn_fast_domains::squareLazy(a,n,u);if(low&2u)a=pgn_fast_domains::twice(a);
 }else{
  if constexpr(Bits==72){a=pgn_fast_domains::squareLazy(a,n,u);if(n.w[1]>>31)a=pgn_fast_domains::twice(a);}
  if constexpr(Bits==73)a=pair(a,((high&1u)<<1)|(n.w[1]>>31),n,u);
  // All three ranges now have the same remaining62bits n[62..1].
  for(int at=30;at>=2;at-=2)a=pair(a,(n.w[1]>>(at-1))&3u,n,u);
  a=pair(a,((n.w[1]&1u)<<1)|(n.w[0]>>31),n,u);
  for(int at=30;at>=2;at-=2)a=pair(a,(n.w[0]>>(at-1))&3u,n,u);
 }
 // At71..73 a<48n, not12n. H>=64 and q<48 imply floor(a.high/(H+1))
 // misses floor(a/n) by at most1; parent's two repairs are conservative.
 return pgn_fast_domains::normalizeFinal12(a,n);
}
F7073_HD bool matches(const U96&a,const U96&n,uint64_t low){U96 expected{{1,0,0}};if(((low>>1)^(low>>2))&1u){expected=n;pgn_fast_domains::sub(expected,U96{{1,0,0}});}return a.w[0]==expected.w[0]&&a.w[1]==expected.w[1]&&a.w[2]==expected.w[2];}
template<unsigned Bits>F7073_HD bool test(uint64_t low,uint32_t high,pgn_fast_domains_stateful::State&state){
 if constexpr(Bits==73)if(high==325u){if(!(low&1u))return false;const auto rem=pgn_fast_domains_stateful::prepare(state,low,325u);const U96 n{{uint32_t(low),uint32_t(low>>32),325u}},r=residue<Bits>(low,325u,state.u,rem);U96 expected{{1,0,0}};if(((low>>1)^(low>>2))&1u){expected=n;pgn_fast_domains::sub(expected,U96{{1,0,0}});}return r.w[0]==expected.w[0]&&r.w[1]==expected.w[1]&&r.w[2]==expected.w[2];}

 constexpr uint32_t lower=1u<<(Bits-65),upper=1u<<(Bits-64);if(!(low&1u)||high<lower||high>=upper)return false;
 const U96 rem=pgn_fast_domains_stateful::prepare(state,low,high),n{{uint32_t(low),uint32_t(low>>32),high}};return matches(residue<Bits>(low,high,state.u,rem),n,low);
}
}
#undef F7073_HD
