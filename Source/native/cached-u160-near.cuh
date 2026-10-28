#pragma once
#include "barrett70-exact.cuh"
#include <stdint.h>
#if defined(__CUDACC__)
#define NEAR_HD __host__ __device__ __forceinline__
#else
#define NEAR_HD inline
#endif
namespace pgn_near_u160 {
using pgn_barrett70::U96;
// Stored as five independent uint32 planes in a future native integration.
struct Anchor { uint32_t w[5]; };
struct Result { U96 quotient,remainder; unsigned repairs; bool used_cache; };
NEAR_HD uint64_t highProduct(uint64_t a,uint64_t b){
#if defined(__CUDA_ARCH__)
 return __umul64hi(a,b);
#else
 const uint64_t a0=uint32_t(a),a1=a>>32,b0=uint32_t(b),b1=b>>32;
 const uint64_t p0=a0*b0,t=a1*b0+(p0>>32);
 const uint64_t mid=uint32_t(t)+a0*b1;
 return a1*b1+(t>>32)+(mid>>32);
#endif
}
NEAR_HD Anchor makeAnchor(uint64_t low){
 const U96 n{{uint32_t(low),uint32_t(low>>32),10}};
 const U96 u=pgn_barrett70::reciprocal160(n);
 const double ud=double(u.w[2])*18446744073709551616.0+
   double(u.w[1])*4294967296.0+double(u.w[0]);
 const double nd=10.0*18446744073709551616.0+double(low);
 const double estimate=(ud/nd)*4294967296.0;
 const uint64_t d=(estimate>=0.0&&estimate<1152921504606846976.0)?uint64_t(estimate):~uint64_t(0);
 return Anchor{{u.w[0],u.w[1],u.w[2],uint32_t(d),uint32_t(d>>32)}};
}
// Contract: anchor.quotient is the exact floor(2^160/(10*2^64+baseLow)),
// produced by makeAnchor and retained without a concurrent writer.
// The slope is only a candidate generator. Its accuracy never accepts a result.
NEAR_HD bool tryNear(uint64_t low,uint64_t baseLow,const Anchor& anchor,Result& out){
 if(low<baseLow||low-baseLow>(1u<<20)||anchor.w[2]>=(1u<<29))return false;
 const uint32_t delta=uint32_t(low-baseLow);
 const uint64_t d=(uint64_t(anchor.w[4])<<32)|anchor.w[3];
 if(d>=(uint64_t(1)<<60))return false;
 const uint64_t change=(uint64_t(delta)*anchor.w[3]>>32)+uint64_t(delta)*anchor.w[4];
 uint64_t ul=(uint64_t(anchor.w[1])<<32)|anchor.w[0];
 uint32_t uh=anchor.w[2];const uint64_t before=ul;ul-=change;uh-=uint32_t(before<change);
 const uint64_t productLow=low*ul;
 const uint64_t productHigh=highProduct(low,ul)+low*uint64_t(uh)+10u*ul;
 uint64_t rl=0-productLow,rh=0-productHigh-uint64_t(productLow!=0);
 // Exact anchor plus the guards above bound the genuine signed residual by
 // 2^117. Since 2^160 is0 modulo2^128, this signed low128 product is exact.
 unsigned repairs=0;
 for(;repairs<4;++repairs){
  if(rh>>63){
   const uint64_t old=rl;rl+=low;rh+=10u+uint64_t(rl<old);
   const uint64_t oldU=ul;--ul;uh-=uint32_t(oldU==0);
  }else if(rh>10u||(rh==10u&&rl>=low)){
   const uint64_t old=rl;rl-=low;rh-=10u+uint64_t(old<low);
   ++ul;uh+=uint32_t(ul==0);
  }else break;
 }
 if((rh>>63)||rh>10u||(rh==10u&&rl>=low))return false;
 // 0<=R-n*u<n is an exact acceptance certificate, not a floating test.
 out={U96{{uint32_t(ul),uint32_t(ul>>32),uh}},
      U96{{uint32_t(rl),uint32_t(rl>>32),uint32_t(rh)}},repairs,true};
 return true;
}
NEAR_HD Result reciprocalOrExact(uint64_t low,uint64_t baseLow,const Anchor& anchor,float* hint=nullptr){
 Result r{};
 if(tryNear(low,baseLow,anchor,r)){
  if(hint)*hint=1.0f/(10.0f*4294967296.0f+float(uint32_t(low>>32))+float(uint32_t(low))*0x1p-32f);
  return r;
 }
 const U96 n{{uint32_t(low),uint32_t(low>>32),10}};
 r.quotient=pgn_barrett70::reciprocal160(n,&r.remainder,hint);r.used_cache=false;return r;
}
NEAR_HD bool test(uint64_t low,uint64_t baseLow,const Anchor&anchor){
 if(!(low&1))return false;
 float hint=0;const auto exact=reciprocalOrExact(low,baseLow,anchor,&hint);
 return pgn_barrett70::testWithReciprocal(low,exact.quotient,exact.remainder,hint);
}
}
#undef NEAR_HD
