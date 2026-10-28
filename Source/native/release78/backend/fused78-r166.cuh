#pragma once
#include "fast-domains-stateful.cuh"
#include "scaledK-repair-checked.cuh"
#include "scaled173-78.cuh"
#ifdef __CUDACC__
#define SK_HD __host__ __device__ __forceinline__
#else
#define SK_HD inline
#endif
// Common W3 construction K=Bits+95. Not a native-throughput qualification.
// Exact U=floor(2^K/n) has96bits. a<256n, X=a*a<2^(2Bits+16).
// Truncated-band deficit <8/2^(K-160)+2^64/n+X/2^K <1 at74..78.
// Therefore floor(X/n)-qhat is0or1 and low96 cancellation gives0<=r<2n.
namespace pgn_fused78 {
using pgn_coach173::U96;using pgn_coach173::U192;using pgn_coach173::U128;
using pgn_coach173::ge;using pgn_coach173::sub;using pgn_coach173::twice;
SK_HD pgn_fast_domains::U96 parent(const U96&a){return pgn_fast_domains::U96{{a.w[0],a.w[1],a.w[2]}};}
SK_HD U96 local(const pgn_fast_domains::U96&a){return U96{{a.w[0],a.w[1],a.w[2]}};}
SK_HD U96 shift(const U96&a,unsigned bits){if(!bits)return a;return U96{{a.w[0]<<bits,(a.w[1]<<bits)|(a.w[0]>>(32-bits)),(a.w[2]<<bits)|(a.w[1]>>(32-bits))}};}
template<unsigned Bits>SK_HD U96 reduce(const U192&x,const U96&n,const U96&u){
 constexpr unsigned s=6;const U128 band=pgn_coach173::highBand9(x,u);
 const U96 q{{(band.w[0]>>s)|(band.w[1]<<(32-s)),(band.w[1]>>s)|(band.w[2]<<(32-s)),(band.w[2]>>s)|(band.w[3]<<(32-s))}};
 U96 r{{x.w[0],x.w[1],x.w[2]}};sub(r,pgn_coach173::productLow96(q,n));return r;
}
template<unsigned Bits>SK_HD U96 square(const U96&a,const U96&n,const U96&u){return reduce<Bits>(pgn_coach173::square6(a),n,u);}
// Proven only after reduction: a<2N<2^79, so the complete square has5words.
template<unsigned Bits>SK_HD U96 squareNarrow(const U96&a,const U96&n,const U96&u){
 const auto x=pgn_coach173::square5Known(a);
 const uint64_t h=uint64_t(pgn_fast_domains::high32(x.w[4],u.w[0]))+pgn_fast_domains::high32(x.w[2],u.w[2])+pgn_fast_domains::high32(x.w[3],u.w[1]);
 const uint64_t s3=pgn_fast_domains::fusedWide(x.w[4],u.w[1],pgn_fast_domains::fusedWide(x.w[3],u.w[2],h));
 const uint64_t s4=pgn_fast_domains::fusedWide(x.w[4],u.w[2],s3>>32);
 const uint32_t b0=uint32_t(s3),b1=uint32_t(s4),b2=uint32_t(s4>>32);
 const U96 q{{(b0>>6)|(b1<<(32-6)),(b1>>6)|(b2<<(32-6)),b2>>6}};
 const uint64_t p0=pgn_fast_domains::fusedWide(q.w[0],n.w[0],0);
 const uint64_t p12=pgn_fast_domains::fusedWide(q.w[1],n.w[0],pgn_fast_domains::fusedWide(q.w[0],n.w[1],p0>>32));
 const uint32_t p2=uint32_t(p12>>32)+q.w[0]*n.w[2]+q.w[1]*n.w[1]+q.w[2]*n.w[0];
 U96 r{{x.w[0],x.w[1],x.w[2]}};sub(r,U96{{uint32_t(p0),uint32_t(p12),p2}});return r;
}
SK_HD U192 shiftedSeed(const U96&a,unsigned bits){
 const unsigned word=bits/32,part=bits%32;const uint32_t s0=a.w[0]<<part,s1=(a.w[1]<<part)|(part?a.w[0]>>(32-part):0u),s2=(a.w[2]<<part)|(part?a.w[1]>>(32-part):0u),s3=part?a.w[2]>>(32-part):0u;
 if(word==0)return U192{{s0,s1,s2,s3,0,0}};if(word==1)return U192{{0,s0,s1,s2,s3,0}};return U192{{0,0,s0,s1,s2,s3}};
}
template<unsigned Bits>SK_HD U96 canonical(U96 a,const U96&n){
 const uint32_t q=a.w[2]/(n.w[2]+1u);uint64_t t=uint64_t(n.w[0])*q;U96 m{{uint32_t(t),0,0}};
 t=uint64_t(n.w[1])*q+(t>>32);m.w[1]=uint32_t(t);m.w[2]=n.w[2]*q+uint32_t(t>>32);
 sub(a,m);if(ge(a,n))sub(a,n);return a;
}
template<unsigned Bits>SK_HD U96 seed(unsigned prefix,const U96&n,const U96&u,const U96&rem){
 constexpr unsigned K=166,s=6;
 const U96 q128{{(u.w[1]>>s)|(u.w[2]<<(32-s)),u.w[2]>>s,0}};U96 r128{};sub(r128,pgn_coach173::productLow96(q128,n));
 if(prefix==255){U96 r=squareNarrow<Bits>(r128,n,u);if(ge(r,n))sub(r,n);if(r.w[0]&1u){uint64_t carry=0;for(unsigned i=0;i<3;i++){const uint64_t t=uint64_t(r.w[i])+n.w[i]+carry;r.w[i]=uint32_t(t);carry=t>>32;}}
  return U96{{(r.w[0]>>1)|(r.w[1]<<31),(r.w[1]>>1)|(r.w[2]<<31),r.w[2]>>1}};}
 return canonical<Bits>(prefix>=K?reduce<Bits>(shiftedSeed(rem,prefix-K),n,u):reduce<Bits>(shiftedSeed(r128,prefix-128),n,u),n);
}
// Same32byte storage as the parent, but u is QK, NEVER fed to parent.prepare.
// Exact previousQK provenance is required. Delta<=2^15 and forecast<2^46
// bound signed residual by <2^(Bits+46)+2^111 <2^125 for Bits<=78.
// R=2^K has low128bits zero, so parent's integer repair applies unchanged.
struct State {pgn_fast_domains_stateful::State core{};};
static_assert(sizeof(State)==32,"One persistent96bit reciprocal");
template<unsigned Bits>SK_HD void liftPaidRemainder(U96&u,U96&r,const U96&n,float inverse){
 constexpr unsigned amount=6;static_assert(Bits>=77&&Bits<=80,"Lift remains below2^95");
 U96 a=shift(r,amount);
 const float estimate=(float(a.w[2])*4294967296.0f+float(a.w[1]))*inverse;
 constexpr uint32_t limit=(1u<<amount)-1u;
 uint32_t digit=estimate>=float(limit)?limit:estimate>0?uint32_t(estimate):0u;
 uint64_t product=uint64_t(n.w[0])*digit;U96 multiple{{uint32_t(product),0,0}};
 product=uint64_t(n.w[1])*digit+(product>>32);multiple.w[1]=uint32_t(product);multiple.w[2]=n.w[2]*digit+uint32_t(product>>32);
 const bool negative=!ge(a,multiple);sub(a,multiple);int sign=negative?-1:0;
 while(sign<0){uint64_t carry=0;for(unsigned i=0;i<3;++i){uint64_t t=uint64_t(a.w[i])+n.w[i]+carry;a.w[i]=uint32_t(t);carry=t>>32;}sign+=int(carry);--digit;}
 while(ge(a,n)){sub(a,n);++digit;}
 u=shift(u,amount);u.w[0]|=digit;r=a;
}
template<unsigned Bits>SK_HD U96 prepare(State&state,uint64_t low,uint32_t high,bool*warm=nullptr){
 static_assert(Bits==78,"Fixed workload");auto&st=state.core;const uint64_t delta=low>=st.low?low-st.low:st.low-low;
 if(st.high==high&&st.u.w[2]&&st.u.w[2]<(1u<<29)&&delta<=32768){
  const float estimate=float(delta)*(float(st.u.w[2])*4294967296.0f+float(st.u.w[1]))*st.inverse;
  if(estimate>=0.0f&&estimate<0x1p46f){const uint64_t change=uint64_t(estimate);uint64_t ul=(uint64_t(st.u.w[1])<<32)|st.u.w[0];uint32_t uh=st.u.w[2];const uint64_t old=ul;
   if(low>=st.low){ul-=change;uh-=uint32_t(old<change);}else{ul+=change;uh+=uint32_t(ul<old);}
   pgn_fast_domains_stateful::Result repaired{};float hint=0;
   if(pgn_coach_scaledK_checked::repairSeedCachedHintChecked(low,high,ul,uh,st.inverse,repaired,&hint)&&repaired.quotient.w[2]&&repaired.quotient.w[2]<(1u<<29)){
    st.u=repaired.quotient;st.low=low;st.high=high;st.inverse=hint;if(warm)*warm=true;return local(repaired.remainder);
   }
  }
 }
 const pgn_fast_domains::U96 n{{uint32_t(low),uint32_t(low>>32),high}};pgn_fast_domains::U96 pr{};float hint=0;
 U96 u=local(pgn_fast_domains::reciprocal160(n,&pr,&hint)),r=local(pr),divisor=local(n);liftPaidRemainder<Bits>(u,r,divisor,hint);
 st.u=parent(u);st.low=low;st.high=high;st.inverse=hint;if(warm)*warm=false;return r;
}
SK_HD unsigned digit3(uint64_t low,uint32_t high,unsigned bit){
 const unsigned start=bit-2;if(start>=64)return (high>>(start-64))&7u;if(start==63)return unsigned((low>>63)|(uint64_t(high)<<1))&7u;if(start==62)return unsigned((low>>62)|(uint64_t(high)<<2))&7u;return unsigned(low>>start)&7u;
}
SK_HD U192 shiftedSquare(U192 x,unsigned digit){
#ifdef __CUDA_ARCH__
 U192 r{};
 asm volatile("{shl.b32 %0,%6,%12; shf.l.wrap.b32 %1,%6,%7,%12; shf.l.wrap.b32 %2,%7,%8,%12; shf.l.wrap.b32 %3,%8,%9,%12; shf.l.wrap.b32 %4,%9,%10,%12; shf.l.wrap.b32 %5,%10,%11,%12;}"
 :"=r"(r.w[0]),"=r"(r.w[1]),"=r"(r.w[2]),"=r"(r.w[3]),"=r"(r.w[4]),"=r"(r.w[5])
 :"r"(x.w[0]),"r"(x.w[1]),"r"(x.w[2]),"r"(x.w[3]),"r"(x.w[4]),"r"(x.w[5]),"r"(digit));return r;
#else
 if(!digit)return x;for(int i=5;i>0;--i)x.w[i]=(x.w[i]<<digit)|(x.w[i-1]>>(32-digit));x.w[0]<<=digit;return x;
#endif
}
SK_HD U96 shiftVariable(const U96&a,unsigned digit){
#ifdef __CUDA_ARCH__
 U96 v{};asm volatile("{shl.b32 %0,%3,%6;shf.l.wrap.b32 %1,%3,%4,%6;shf.l.wrap.b32 %2,%4,%5,%6;}" :"=r"(v.w[0]),"=r"(v.w[1]),"=r"(v.w[2]):"r"(a.w[0]),"r"(a.w[1]),"r"(a.w[2]),"r"(digit));return v;
#else
 return shift(a,digit);
#endif
}
// X*(U<<digit)=(X<<digit)*U. FixedH16263 ensures shiftedU fits96bits,
// X has5words, both64bit quotient columns fit, and real deficit<0.579.
// Hence integer deficit<=1 and residual<2N, with no per-bit normalization.
template<unsigned Bits>SK_HD U96 fusedSquare(U96 a,unsigned digit,const U96&n,const U96&u){
 const auto x=pgn_coach173::square5Known(a);const U96 v=shiftVariable(u,digit);
 const uint64_t h=uint64_t(pgn_fast_domains::high32(x.w[4],v.w[0]))+pgn_fast_domains::high32(x.w[2],v.w[2])+pgn_fast_domains::high32(x.w[3],v.w[1]);
 const uint64_t s3=pgn_fast_domains::fusedWide(x.w[4],v.w[1],pgn_fast_domains::fusedWide(x.w[3],v.w[2],h));
 const uint64_t s4=pgn_fast_domains::fusedWide(x.w[4],v.w[2],s3>>32);
 const uint32_t b0=uint32_t(s3),b1=uint32_t(s4),b2=uint32_t(s4>>32);
 const U96 q{{(b0>>6)|(b1<<26),(b1>>6)|(b2<<26),b2>>6}};
 const uint64_t p0=pgn_fast_domains::fusedWide(q.w[0],n.w[0],0);
 const uint64_t p12=pgn_fast_domains::fusedWide(q.w[1],n.w[0],pgn_fast_domains::fusedWide(q.w[0],n.w[1],p0>>32));
 const uint32_t p2=uint32_t(p12>>32)+q.w[0]*n.w[2]+q.w[1]*n.w[1]+q.w[2]*n.w[0];
 U96 r=shiftVariable(U96{{x.w[0],x.w[1],x.w[2]}},digit);sub(r,U96{{uint32_t(p0),uint32_t(p12),p2}});return r;
}
template<unsigned Bits>SK_HD U96 tripletWord(U96 a,unsigned digit,const U96&n,const U96&u){
 a=squareNarrow<Bits>(a,n,u);a=squareNarrow<Bits>(a,n,u);return fusedSquare<Bits>(a,digit,n,u);
}
template<unsigned Bits>SK_HD U96 residue(uint64_t low,uint32_t high,const U96&u,const U96&rem){
 static_assert(Bits==78,"Fixed78 full Fast word32 schedule");
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};
 U96 a=seed<Bits>(254,n,u,rem);
 a=tripletWord<Bits>(a,0,n,u);a=tripletWord<Bits>(a,7,n,u);
 for(int at=29;at>=2;at-=3)a=tripletWord<Bits>(a,(n.w[1]>>at)&7u,n,u);
 a=tripletWord<Bits>(a,(n.w[0]>>31)|((n.w[1]&3u)<<1),n,u);
 for(int at=28;at>=1;at-=3)a=tripletWord<Bits>(a,(n.w[0]>>at)&7u,n,u);
 if(ge(a,n))sub(a,n);return a;
}
template<unsigned Bits>SK_HD bool test(uint64_t low,uint32_t high,State&state){
 if(!(low&1u)||high!=16263u)return false;const U96 rem=prepare<Bits>(state,low,high),r=residue<Bits>(low,high,local(state.core.u),rem);U96 expected{{1,0,0}},n{{uint32_t(low),uint32_t(low>>32),high}};if(((low>>1)^(low>>2))&1u){expected=n;sub(expected,U96{{1,0,0}});}return r.w[0]==expected.w[0]&&r.w[1]==expected.w[1]&&r.w[2]==expected.w[2];
}
// Native walker already owns a parent-shaped32byte State per owned job.
// Copy values explicitly, never type-pun unrelated structs. A MODE74..78 job
// uses only this adapter; MODE4 uses only the original U160 prepare/test.
template<unsigned Bits>SK_HD bool testWithParentState(uint64_t low,uint32_t high,pgn_fast_domains_stateful::State&core){State state;state.core=core;const bool result=test<Bits>(low,high,state);core=state.core;return result;}
}
#undef SK_HD
