#pragma once
#include "fast-wide-cold-v497.cuh"
#ifdef __CUDACC__
#define PGN_CACHE_HD __host__ __device__ __forceinline__
#else
#define PGN_CACHE_HD inline
#endif
namespace pgn_fast_wide_cache498 {
using namespace pgn_fast_wide_cold497;
PGN_CACHE_HD uint64_t highProduct64(uint64_t a,uint64_t b){
#ifdef __CUDA_ARCH__
 return __umul64hi(a,b);
#else
 const uint64_t a0=uint32_t(a),a1=a>>32,b0=uint32_t(b),b1=b>>32;
 const uint64_t p0=a0*b0,t=a1*b0+(p0>>32),mid=uint32_t(t)+a0*b1;
 return a1*b1+(t>>32)+(mid>>32);
#endif
}
PGN_CACHE_HD U128 quotient(const State&s){return U128{{s.u.w[0],s.u.w[1],s.u.w[2],s.u3}};}
PGN_CACHE_HD bool adjust(U128&u,uint32_t q,bool minus){
 uint64_t low=(uint64_t(u.w[1])<<32)|u.w[0],high=(uint64_t(u.w[3])<<32)|u.w[2];const uint64_t old=low;
 if(minus){low-=q;const unsigned borrow=old<q;if(borrow&&high==0)return false;high-=borrow;}
 else{low+=q;const unsigned carry=low<old;if(carry&&high==UINT64_MAX)return false;high+=carry;}
 u=U128{{uint32_t(low),uint32_t(low>>32),uint32_t(high),uint32_t(high>>32)}};return true;
}
// Caller provenance: u started from exactCold, then only certified repairs.
// Delta<=2^15, change<2^30 and K<=2Bits+10 imply true signed residual<2^126.
// R has zero low128 bits; the exact low128 product therefore recovers it.
PGN_CACHE_HD bool repair(uint64_t low,uint32_t high,U128&u,float inverse,U96&remainder){
 const uint64_t ul=(uint64_t(u.w[1])<<32)|u.w[0],uh=(uint64_t(u.w[3])<<32)|u.w[2];
 const uint64_t pl=low*ul,ph=highProduct64(low,ul)+low*uh+uint64_t(high)*ul;
 uint64_t rl=0-pl,rh=0-ph-uint64_t(pl!=0);
 if(!(rh>>63)&&(rh<high||(rh==high&&rl<low))){remainder=U96{{uint32_t(rl),uint32_t(rl>>32),uint32_t(rh)}};return true;}
 const bool negative=(rh>>63)!=0;uint64_t ml=rl,mh=rh;
 if(negative){ml=0-rl;mh=0-rh-uint64_t(rl!=0);}
 const float scaled=(float(uint32_t(mh>>32))*4294967296.0f+float(uint32_t(mh)))*4294967296.0f+float(uint32_t(ml>>32));
 const float estimate=scaled*inverse;if(!(estimate>=0.0f)||estimate>=4194304.0f)return false;
 const uint32_t q=uint32_t(estimate);const uint64_t productLow=low*uint64_t(q),productHigh=highProduct64(low,q)+uint64_t(high)*q;
 if(negative){const uint64_t old=rl;rl+=productLow;rh+=productHigh+uint64_t(rl<old);if(!adjust(u,q,true))return false;}
 else{const uint64_t old=rl;rl-=productLow;rh-=productHigh+uint64_t(old<productLow);if(!adjust(u,q,false))return false;}
 for(unsigned repairs=0;repairs<4;++repairs){
  if(rh>>63){const uint64_t old=rl;rl+=low;rh+=high+uint64_t(rl<old);if(!adjust(u,1,true))return false;}
  else if(rh>high||(rh==high&&rl>=low)){const uint64_t old=rl;rl-=low;rh-=high+uint64_t(old<low);if(!adjust(u,1,false))return false;}
  else break;
 }
 if((rh>>63)||rh>high||(rh==high&&rl>=low))return false;
 remainder=U96{{uint32_t(rl),uint32_t(rl>>32),uint32_t(rh)}};return true;
}
template<unsigned Bits,unsigned K>PGN_CACHE_HD U96 prepare(State&state,uint64_t low,uint32_t high,bool*warm=nullptr){
 static_assert(Bits>=79&&Bits<=95&&K<=2*Bits+10,"Signed128 residual proof domain");
 const uint64_t delta=low>=state.low?low-state.low:state.low-low;
 if(state.high==high&&(state.u.w[2]|state.u3)&&state.inverse>0.0f&&state.inverse<1.0f&&delta<=32768){
  const float upper=(float(state.u3)*4294967296.0f+float(state.u.w[2]))*4294967296.0f+float(state.u.w[1]);
  const float estimate=float(uint32_t(delta))*upper*state.inverse;
  if(estimate>=0.0f&&estimate<1073741824.0f){
   U128 u=quotient(state);U96 remainder{};
   if(adjust(u,uint32_t(estimate),low>=state.low)&&repair(low,high,u,state.inverse,remainder)){
    state.u=U96{{u.w[0],u.w[1],u.w[2]}};state.u3=u.w[3];state.low=low;state.high=high;
    if(warm)*warm=true;return remainder;
   }
  }
 }
 if(warm)*warm=false;return prepareCold<Bits,K>(state,low,high);
}
}
#undef PGN_CACHE_HD
