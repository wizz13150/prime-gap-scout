#pragma once
#include "fast-domains-stateful.cuh"
#include "r64mu69.cuh"
#ifdef __CUDACC__
#define S69_HD __host__ __device__ __forceinline__
#else
#define S69_HD inline
#endif
namespace pgn_fast69 {
using pgn_fast_domains::U96;
S69_HD U96 residue(uint64_t low,uint32_t high,const U96&u,const U96&rem){
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};
 // For odd69-bit n, e=(n-1)/2=n>>1 has68bits. Its top8bits are n[68..61].
 const unsigned prefix=(high<<3)|unsigned(low>>61);
 U96 a=pgn_fast_domains::seedPrefix(n,u,rem,prefix);
 // The remaining60exponentbits are n[60..1]. Preserve the parent's W3
 // grouping:19triples followed by2bits and the final bit. All extracts32bit.
 for(int at=28;at>=2;at-=3){a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::shiftSmall(a,(n.w[1]>>(at-2))&7u);}
 a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::shiftSmall(a,((n.w[1]&3u)<<1)|(n.w[0]>>31));
 for(int at=30;at>=4;at-=3){a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::shiftSmall(a,(n.w[0]>>(at-2))&7u);}
 a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::squareLazy(a,n,u);a=pgn_fast_domains::shiftSmall(a,(n.w[0]>>2)&3u);
 a=pgn_fast_domains::squareLazy(a,n,u);if(low&2u)a=pgn_fast_domains::twice(a);
 return pgn_fast_domains::normalizeFinal12(a,n);
}
S69_HD bool matches(const U96&a,const U96&n,uint64_t low){U96 expected{{1,0,0}};if(((low>>1)^(low>>2))&1u){expected=n;pgn_fast_domains::sub(expected,U96{{1,0,0}});}return a.w[0]==expected.w[0]&&a.w[1]==expected.w[1]&&a.w[2]==expected.w[2];}
S69_HD bool test(uint64_t low,uint32_t high,pgn_fast_domains_stateful::State&state){
 if(high==21u){
  // Typed scalar fields, no reinterpret/union aliasing. Tags cannot be mistaken for old reciprocal state.
  root69_mu::State point{};point.anchor=state.low;point.mu=state.u.w[0];point.ready=state.high;
  const bool answer=root69_mu::test(low,point);
  state.low=point.anchor;state.u.w[0]=point.mu;state.high=point.ready;
  return answer;
 }
if(!(low&1u)||high<16||high>=32)return false;const U96 rem=pgn_fast_domains_stateful::prepare(state,low,high);const U96 n{{uint32_t(low),uint32_t(low>>32),high}};return matches(residue(low,high,state.u,rem),n,low);}
}
#undef S69_HD
