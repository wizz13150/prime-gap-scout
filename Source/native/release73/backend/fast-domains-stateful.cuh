#pragma once
#include "cached-u160-near.cuh"
#include "fast-domains-u160.cuh"
#if defined(__CUDACC__)
#define STATE_HD __host__ __device__ __forceinline__
#else
#define STATE_HD inline
#endif
namespace pgn_fast_domains_stateful {
using pgn_fast_domains::U96;using pgn_near_u160::highProduct;
struct Result {U96 quotient,remainder;unsigned repairs;bool repaired;};
struct State {U96 u{};uint64_t low=0;float inverse=0;uint32_t high=0;};
// Caller preserves exact previousU and guards delta<=2^15/change<2^46.
// This bounds genuineR-n*seed by2^115, so signedlow128 is exact.
STATE_HD bool repairSeed(uint64_t low,uint32_t high,uint64_t ul,uint32_t uh,Result&out,float*hint,float inverse){
 const uint64_t pl=low*ul,ph=highProduct(low,ul)+low*uint64_t(uh)+uint64_t(high)*ul;
 uint64_t rl=0-pl,rh=0-ph-uint64_t(pl!=0);
 // The exact previousU plus guarded delta/change preserves signed128 residual.
 const bool negative=(rh>>63)!=0;
 uint64_t ml=rl,mh=rh;
 if(negative){ml=0-rl;mh=0-rh-uint64_t(rl!=0);}
 if(mh>>32)return false; // Bad seed: original exact fallback, no acceptance.

 const float estimate=(float(uint32_t(mh))*4294967296.0f+float(uint32_t(ml>>32)))*inverse;
 if(!(estimate>=0.0f)||estimate>=4194304.0f)return false;
 const uint32_t q=uint32_t(estimate);
 const uint64_t productLow=low*uint64_t(q),productHigh=highProduct(low,q)+uint64_t(high)*uint64_t(q);
 if(negative){
  const uint64_t old=rl;rl+=productLow;rh+=productHigh+uint64_t(rl<old);
  const uint64_t oldU=ul;ul-=q;uh-=uint32_t(oldU<q);
 }else{
  const uint64_t old=rl;rl-=productLow;rh-=productHigh+uint64_t(old<productLow);
  const uint64_t oldU=ul;ul+=q;uh+=uint32_t(ul<oldU);
 }
 unsigned repairs=0;
 for(;repairs<4;++repairs){
  if(rh>>63){const uint64_t old=rl;rl+=low;rh+=high+uint64_t(rl<old);const uint64_t u=ul;--ul;uh-=uint32_t(u==0);}
  else if(rh>high||(rh==high&&rl>=low)){const uint64_t old=rl;rl-=low;rh-=high+uint64_t(old<low);++ul;uh+=uint32_t(ul==0);}
  else break;
 }
 if((rh>>63)||rh>high||(rh==high&&rl>=low))return false;
 out={U96{{uint32_t(ul),uint32_t(ul>>32),uh}},U96{{uint32_t(rl),uint32_t(rl>>32),uint32_t(rh)}},repairs,true};
 if(hint)*hint=inverse;
 return true;
}
STATE_HD bool repairSeed(uint64_t low,uint32_t high,uint64_t ul,uint32_t uh,Result&out,float*hint){
 const float inverse=1.0f/(float(high)*4294967296.0f+float(uint32_t(low>>32))+float(uint32_t(low))*0x1p-32f);
 return repairSeed(low,high,ul,uh,out,hint,inverse);
}
STATE_HD U96 prepare(State&state,uint64_t low,uint32_t high,bool*usedCache=nullptr){
 const uint64_t delta=low>=state.low?low-state.low:state.low-low;
 if(state.high==high&&state.u.w[2]&&state.u.w[2]<(1u<<29)&&delta<=32768){
  // Only a candidate: every lost float bit is closed by the signed integer
  // residual, exact bulk update and final0<=r<n certificate or fallback.
  const float estimate=float(delta)*(float(state.u.w[2])*4294967296.0f+float(state.u.w[1]))*state.inverse;
  if(estimate>=0.0f&&estimate<70368744177664.0f){
   const uint64_t change=uint64_t(estimate);uint64_t ul=(uint64_t(state.u.w[1])<<32)|state.u.w[0];uint32_t uh=state.u.w[2];const uint64_t old=ul;
   if(low>=state.low){ul-=change;uh-=uint32_t(old<change);}else{ul+=change;uh+=uint32_t(ul<old);}
   Result r{};float hint=0;
   if(high==325u?repairSeed(low,high,ul,uh,r,&hint,state.inverse):repairSeed(low,high,ul,uh,r,&hint)){
    // Replace old anchor BEFORE the Euler squares. The exact currentU/n
    // is simultaneously the existing Euler operand and next point's state.
    state.u=r.quotient;state.low=low;state.inverse=hint;state.high=high;
    if(usedCache)*usedCache=true;return r.remainder;
   }
  }
 }
 U96 rem{};float hint=0;const U96 n{{uint32_t(low),uint32_t(low>>32),high}};
 state.u=pgn_fast_domains::reciprocal160(n,&rem,&hint);state.low=low;state.inverse=hint;state.high=high;
 if(usedCache)*usedCache=false;return rem;
}
STATE_HD bool test(uint64_t low,uint32_t high,State&state){
 if(!(low&1))return false;const U96 rem=prepare(state,low,high);
 return pgn_fast_domains::testWithReciprocal(low,high,state.u,rem,state.inverse);
}
}
#undef STATE_HD
