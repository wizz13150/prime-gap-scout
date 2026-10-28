#pragma once
#include "fast-wide-cache-v498.cuh"
#include "fast-wide-grouped-band-v490.cuh"
#include "fast-band96-v518.cuh"
#include "fast-point-high-v533.cuh"
#ifdef __CUDACC__
#define PGN_LAZY_HD __host__ __device__ __forceinline__
#else
#define PGN_LAZY_HD inline
#endif
namespace pgn_fast_batch499 {
using pgn_coach173::U96;using pgn_coach173::U128;using pgn_coach173::U192;
using State=pgn_fast_wide_cold497::State;
template<unsigned Bits>struct P{
 static_assert(Bits>=80&&Bits<=94,"Lazy96 engine domain");
 static constexpr unsigned K=2*Bits+5,QuotientWords=Bits<=90?3:4;
};
template<>struct P<80>{static constexpr unsigned K=168,QuotientWords=3;};
template<unsigned Bits>PGN_LAZY_HD U96 seed(unsigned prefix,const U96&n,const U128&u){
 U96 a{{0,0,prefix<96?1u<<(prefix-64):0u}};
 if(prefix<Bits)return a;
 const unsigned shift=P<Bits>::K-prefix;
 const uint64_t lo=(uint64_t(u.w[1])<<32)|u.w[0],hi=(uint64_t(u.w[3])<<32)|u.w[2];
 const uint64_t q=shift>=64?hi>>(shift-64):(lo>>shift)|(hi<<(64-shift));
 pgn_coach173::sub(a,pgn_coach173::productLow96(U96{{uint32_t(q),uint32_t(q>>32),0}},n));return a;
}
template<unsigned Bits>PGN_LAZY_HD U96 step(U96 a,unsigned bit,const U96&n,const U128&u){
 const auto x=pgn_coach173::square6(a);
 U96 q{};
 if constexpr(Bits<=82){
  const auto band=pgn_fast_band96_518::highBand(x,U96{{u.w[0],u.w[1],u.w[2]}});
  q=pgn_fast_grouped_wide490::quotientLow96<P<Bits>::K>(pgn_fast_grouped_wide490::Band160{{band.w[0],band.w[1],band.w[2],0,0}});
 }else q=pgn_fast_grouped_wide490::quotientLow96<P<Bits>::K>(pgn_fast_grouped_wide490::highBand<P<Bits>::QuotientWords>(x,u));
 U96 r{{x.w[0],x.w[1],x.w[2]}};pgn_coach173::sub(r,pgn_coach173::productLow96(q,n));
 return pgn_fast_grouped_wide490::shiftLow96(U192{{r.w[0],r.w[1],r.w[2],0,0,0}},bit);
}
#include "fast-radix80-columns-v541.cuh"
#include "fast-exactscale80-v749.cuh"
template<unsigned Bits,uint32_t FixedHigh=0>PGN_LAZY_HD U96 residue(uint64_t low,uint32_t high,const U128&u,const U96&rem){
 if constexpr(Bits==80){if constexpr(!FixedHigh||FixedHigh==54210u)if(high==54210u)return exactscale80Residue749(low,high,u,rem);return radix80Residue<FixedHigh>(low,high,u,rem);}
 constexpr unsigned HBits=Bits-71;
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};
 U96 a=seed<Bits>(high>>HBits,n,u);
 for(int at=int(HBits)-1;at>=0;--at)a=step<Bits>(a,(high>>at)&1u,n,u);
 for(int at=31;at>=0;--at)a=step<Bits>(a,(n.w[1]>>at)&1u,n,u);
 for(int at=31;at>=1;--at)a=step<Bits>(a,(n.w[0]>>at)&1u,n,u);
 for(unsigned j=0;j<3;++j)if(pgn_coach173::ge(a,n))pgn_coach173::sub(a,n);
 return a;
}
template<unsigned Bits,uint32_t FixedHigh=0>PGN_LAZY_HD bool test(uint64_t low,uint32_t high,State&state){
 if constexpr(!FixedHigh){
  constexpr uint32_t PointHigh=pgn_fast_calibration533::PointHigh<Bits>::value;
  if(high==PointHigh)return test<Bits,PointHigh>(low,high,state);
 }

 static_assert(!FixedHigh||(uint64_t(FixedHigh)>=(1ull<<(Bits-65))&&uint64_t(FixedHigh)<(1ull<<(Bits-64))),"Fixed high belongs to this engine");
 if(!(low&1u))return false;
 if constexpr(FixedHigh){if(high!=FixedHigh)return false;}
 else if(high<(1u<<(Bits-65))||uint64_t(high)>=(1ull<<(Bits-64)))return false;
 const uint32_t h=FixedHigh?FixedHigh:high;
 auto rem=pgn_fast_wide_cache498::prepare<Bits,P<Bits>::K>(state,low,h);
 auto reciprocal=pgn_fast_wide_cache498::quotient(state);
 if constexpr(Bits==80){reciprocal.w[3]=0;reciprocal.w[2]&=0x1ffffffu;rem.w[2]&=0xffffu;}
 const auto r=residue<Bits,FixedHigh>(low,h,reciprocal,rem);
 const U96 n{{uint32_t(low),uint32_t(low>>32),h}};U96 expected{{1,0,0}};
 if(((low>>1)^(low>>2))&1u){expected=n;pgn_coach173::sub(expected,U96{{1,0,0}});}
 return r.w[0]==expected.w[0]&&r.w[1]==expected.w[1]&&r.w[2]==expected.w[2];
}
}
#undef PGN_LAZY_HD
