#pragma once
#include "fast-domains-stateful.cuh"
#ifdef __CUDACC__
#define WH_HD __host__ __device__ __forceinline__
#else
#define WH_HD inline
#endif
namespace pgn_coach_scaledK_checked {
using pgn_fast_domains_stateful::Result;using pgn_fast_domains_stateful::U96;using pgn_near_u160::highProduct;
WH_HD bool repairSeedCachedHintChecked(uint64_t low,uint32_t high,uint64_t ul,uint32_t uh,float priorInverse,Result&out,float*hint){
 const uint64_t pl=low*ul,ph=highProduct(low,ul)+low*uint64_t(uh)+uint64_t(high)*ul;
 uint64_t rl=0-pl,rh=0-ph-uint64_t(pl!=0);
 if(!(rh>>63)&&(rh<high||(rh==high&&rl<low))){
  out={U96{{uint32_t(ul),uint32_t(ul>>32),uh}},U96{{uint32_t(rl),uint32_t(rl>>32),uint32_t(rh)}},0,true};
  if(hint)*hint=priorInverse;return true;
 }
 // The exact previousU plus guarded delta/change preserves signed128 residual.
 const bool negative=(rh>>63)!=0;
 uint64_t ml=rl,mh=rh;
 if(negative){ml=0-rl;mh=0-rh-uint64_t(rl!=0);}
 if(mh>>32)return false; // Bad seed: original exact fallback, no acceptance.
 const float inverse=priorInverse;
 const float estimate=(float(uint32_t(mh))*4294967296.0f+float(uint32_t(ml>>32)))*inverse;
 if(!(estimate>=0.0f)||estimate>=4194304.0f)return false;
 const uint32_t q=uint32_t(estimate);
 const uint64_t productLow=low*uint64_t(q),productHigh=highProduct(low,q)+uint64_t(high)*uint64_t(q);
 if(negative){
  const uint64_t old=rl;rl+=productLow;rh+=productHigh+uint64_t(rl<old);
  const uint64_t oldU=ul;ul-=q;const uint32_t borrow=uint32_t(oldU<q);if(borrow&&uh==0)return false;uh-=borrow;
 }else{
  const uint64_t old=rl;rl-=productLow;rh-=productHigh+uint64_t(old<productLow);
  const uint64_t oldU=ul;ul+=q;const uint32_t carry=uint32_t(ul<oldU);if(carry&&uh==0xffffffffu)return false;uh+=carry;
 }
 unsigned repairs=0;
 for(;repairs<4;++repairs){
  if(rh>>63){const uint64_t old=rl;rl+=low;rh+=high+uint64_t(rl<old);const uint64_t u=ul;if(u==0&&uh==0)return false;--ul;uh-=uint32_t(u==0);}
  else if(rh>high||(rh==high&&rl>=low)){const uint64_t old=rl;rl-=low;rh-=high+uint64_t(old<low);if(ul==0xffffffffffffffffull&&uh==0xffffffffu)return false;++ul;uh+=uint32_t(ul==0);}
  else break;
 }
 if((rh>>63)||rh>high||(rh==high&&rl>=low))return false;
 out={U96{{uint32_t(ul),uint32_t(ul>>32),uh}},U96{{uint32_t(rl),uint32_t(rl>>32),uint32_t(rh)}},repairs,true};
 if(hint)*hint=inverse;
 return true;
}
}
#undef WH_HD
