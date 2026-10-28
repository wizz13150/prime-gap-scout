
#pragma once
#include "mu128-state8.cuh"
#ifdef __CUDACC__
#define MK_HD __host__ __device__ __forceinline__
#else
#define MK_HD inline
#endif
// Same cache/certificate mechanism. K is the ACTUAL retained coefficient domain,
// not a width sweep:160 at72..77,166 at78/79,165 at80.
namespace whole68_mu128_coeff {
using whole68_mu128::State;using whole68_mu128::U96;using whole68_mu128::U128;
using whole68_mu128::hi64;using whole68_mu128::ge;using whole68_mu128::sub;
using whole68_mu128::add;using whole68_mu128::negative;
struct Context {U96 quotient,remainder;};
template<uint32_t High,unsigned K>MK_HD bool prepareWarm(uint64_t low,State&state,Context&out){
 static_assert(K>=160&&K<=166,"Only paid coefficients160/165/166");
 static_assert(High>=2&&High<0x80000000u,"Signed certificate radius");
 static_assert(High>=(1u<<(K-160)),"Quotient K fits96 bits for low odd");
 static_assert(uint64_t(High)<(1ull<<(192-K)),"N<2^(256-K), numerator128 and hint error<1");
 constexpr unsigned Shift=K-128;
 uint64_t m=state.quotient128;
 if(m<whole68_mu128::qbound<High+1>()||m>whole68_mu128::qbound<High>())return false;
 uint64_t top=0;const U128 p=whole68_mu128::product<High>(low,m,top);
 if(top>1)return false;
 U128 r=sub(U128{0,0},p),n{low,High};
 if(negative(r)){r=add(r,n);--m;}
 else if(ge(r,n)){r=sub(r,n);++m;}
 if(negative(r)||ge(r,n)||r.high>>32)return false;
 const uint64_t upper=uint64_t(uint32_t(r.high))*m,carryProduct=hi64(r.low,m);
 const uint64_t band=upper+carryProduct;
 if(band<upper)return false;
 uint64_t q=band>>(64-Shift); // up to38bits. NEVER truncate to uint32_t.
 uint64_t qt=0;const U128 qn=whole68_mu128::product<High>(low,q,qt);
 if(qt||r.high>>(64-Shift))return false;
 const U128 numerator{r.low<<Shift,(r.low>>(64-Shift))|(r.high<<Shift)};
 U128 rem=sub(numerator,qn);
 if(negative(rem))return false;
 if(ge(rem,n)){rem=sub(rem,n);if(q==((uint64_t(1)<<Shift)-1))return false;++q;}
 if(negative(rem)||ge(rem,n)||rem.high>>32)return false;
 if constexpr(Shift>32)if(m>>(96-Shift))return false;
 const U96 u{{uint32_t(q),uint32_t(q>>32)|uint32_t(m<<(Shift-32)),uint32_t(m>>(64-Shift))}};
 out=Context{u,{{uint32_t(rem.low),uint32_t(rem.low>>32),uint32_t(rem.high)}}};
 state.quotient128=m;return true;
}
template<unsigned K>MK_HD void acceptCold(State&state,const Context&exact){
 constexpr unsigned Shift=K-128;
 static_assert(Shift>=32&&Shift<=38,"Declared paid coefficient domain");
 state.quotient128=(uint64_t(exact.quotient.w[1])>>(Shift-32))|(uint64_t(exact.quotient.w[2])<<(64-Shift));
}
}
#undef MK_HD
