#pragma once
#include "fast-domains-u160.cuh"
#ifdef __CUDACC__
#define M315_HD __host__ __device__ __forceinline__
#else
#define M315_HD inline
#endif
namespace pgn_root315 {
// N=H*2^64+L, A<kN, H>=k-2. q=floor(A.high/(H+1))
// never exceeds floor(A/N) and misses it by at most one.
// This helper is used ONLY at proved final boundaries, never generic seed/guard.
M315_HD pgn_fast_domains::U96 normalizeFinalOne(pgn_fast_domains::U96 a,const pgn_fast_domains::U96&n){
 const uint32_t q=a.w[2]/(n.w[2]+1u);
 uint64_t product=uint64_t(n.w[0])*q;pgn_fast_domains::U96 multiple{{uint32_t(product),0,0}};
 product=uint64_t(n.w[1])*q+(product>>32);multiple.w[1]=uint32_t(product);
 multiple.w[2]=n.w[2]*q+uint32_t(product>>32);
 pgn_fast_domains::sub(a,multiple);if(pgn_fast_domains::ge(a,n))pgn_fast_domains::sub(a,n);return a;
}
}
#undef M315_HD
