
#pragma once
#include <stdint.h>
#ifdef __CUDACC__
#define M128_HD __host__ __device__ __forceinline__
#else
#define M128_HD inline
#endif
// Cache contains an EXACT quotient for the last accepted N, not an unchecked hint.
// A new N always gets a signed-product certificate. Repair limit is ONE;
// descriptor/reverse/large jumps go directly to the original exact cold builder.
namespace whole68_mu128 {
struct U96 {uint32_t w[3];};
struct U128 {uint64_t low,high;};
struct State {uint64_t quotient128=0;};
struct Context {U96 quotient160,remainder160;};
static_assert(sizeof(State)==8,"Only M128 persists; current u160/rem160 are temporary");
M128_HD uint64_t hi64(uint64_t a,uint64_t b){
#ifdef __CUDA_ARCH__
 return __umul64hi(a,b);
#else
 const uint64_t a0=uint32_t(a),a1=a>>32,b0=uint32_t(b),b1=b>>32;
 const uint64_t p0=a0*b0,p1=a1*b0,p2=a0*b1;
 const uint64_t mid=(p0>>32)+uint32_t(p1)+uint32_t(p2);
 return a1*b1+(p1>>32)+(p2>>32)+(mid>>32);
#endif
}
M128_HD bool ge(U128 a,U128 b){return a.high>b.high||(a.high==b.high&&a.low>=b.low);}
M128_HD U128 sub(U128 a,U128 b){const uint64_t old=a.low;a.low-=b.low;a.high-=b.high+uint64_t(old<b.low);return a;}
M128_HD U128 add(U128 a,U128 b){const uint64_t old=a.low;a.low+=b.low;a.high+=b.high+uint64_t(a.low<old);return a;}
M128_HD bool negative(U128 a){return(a.high>>63)!=0;}
template<uint32_t High>M128_HD constexpr uint64_t qbound(){
 static_assert(High>=2,"Signed certificate bound needs N/R64>=2");
 return UINT64_MAX/High+uint64_t(UINT64_MAX%High==High-1u);
}
// Return full q64*N96 modulo128 PLUS its high64 word. No carry is discarded.
template<uint32_t High>M128_HD U128 product(uint64_t low,uint64_t q,uint64_t& top){
 const uint64_t p0=low*q,p1=hi64(low,q),p2=uint64_t(High)*q;
 const uint64_t high=p1+p2;
 top=hi64(uint64_t(High),q)+uint64_t(high<p1);
 return {p0,high};
}
template<uint32_t High>M128_HD bool prepareWarm(uint64_t low,State&state,Context&out){
 static_assert(High>=2&&High<0x80000000u,"Exact fixed-high signed radius");
 uint64_t m=state.quotient128;
 if(m<qbound<High+1>()||m>qbound<High>())return false;
 // qbound gives negative radius <2^128/High and positive radius
 // <2^128/(High+1)+N. High>=2,N<2^95 imply both <2^127.
 // Thus signedlow128 decodes the exact residual even after arbitrary jumps.
 uint64_t top=0;const U128 p=product<High>(low,m,top);
 if(top>1)return false;
 U128 r=sub(U128{0,0},p),n{low,High};
 // Repair M_prev once only. This is not the later q160 correction.
 if(negative(r)){r=add(r,n);--m;}
 else if(ge(r,n)){r=sub(r,n);++m;}
 if(negative(r)||ge(r,n))return false; // bounded cold fallback, NEVER a rejection of N
 // Now r is the canonical 128 remainder (<N<2^96), and M is exact.
 if(r.high>>32)return false;
 const uint64_t upper=uint64_t(uint32_t(r.high))*m,carryProduct=hi64(r.low,m);
 const uint64_t band=upper+carryProduct;
 if(band<upper)return false; // impossible under r*M<2^128, retain checked fallback
 uint32_t q=uint32_t(band>>32);
 // q=floor(r*M/2^96), qTrue=floor(r*2^32/N), qTrue-q in {0,1}.
 uint64_t qt=0;const U128 qn=product<High>(low,uint64_t(q),qt);
 if(qt)return false;
 const U128 numerator{r.low<<32,(r.low>>32)|(r.high<<32)};
 U128 rem=sub(numerator,qn);
 if(negative(rem))return false;
 if(ge(rem,n)){rem=sub(rem,n);if(q==UINT32_MAX)return false;++q;}
 if(negative(rem)||ge(rem,n)||rem.high>>32)return false;
 Context candidate{{{q,uint32_t(m),uint32_t(m>>32)}},{{uint32_t(rem.low),uint32_t(rem.low>>32),uint32_t(rem.high)}}};
 out=candidate;state.quotient128=m;return true;
}
M128_HD void acceptCold(State&state,const Context&exact){
 // floor nesting: floor(floor(2^160/N)/2^32)=floor(2^128/N).
 state.quotient128=uint64_t(exact.quotient160.w[1])|(uint64_t(exact.quotient160.w[2])<<32);
}
}
#undef M128_HD
