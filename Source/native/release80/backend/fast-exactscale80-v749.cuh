#pragma once
// Included INSIDE pgn_fast_batch499, after the exact retained168 operators.
template<bool Fused>PGN_LAZY_HD U96 exactscale80Square749(const U96&a,unsigned digit,const U96&n,const U96&u166,unsigned guard7){
 const auto x=pgn_coach173::square5Known(a);
 U96 v=u166;
 if constexpr(Fused){
  const auto shifted=pgn_fast_grouped_wide490::shift128(U128{{u166.w[0],u166.w[1],u166.w[2],0}},digit);
  v=U96{{shifted.w[0]|(guard7>>(7-digit)),shifted.w[1],shifted.w[2]}};
 }
 const U96 band=radix80Column96(x,v);
 const U96 q{{(band.w[0]>>6)|(band.w[1]<<26),(band.w[1]>>6)|(band.w[2]<<26),band.w[2]>>6}};
 U96 r{{x.w[0],x.w[1],x.w[2]}};
 if constexpr(Fused)r=pgn_fast_grouped_wide490::shiftLow96(x,digit);
 pgn_coach173::sub(r,radix80Low96(q,n));
 // Proven raw<60200*2^64; no normalization hidden by this redundant mask.
 r.w[2]&=0xffffu;return r;
}
PGN_LAZY_HD U96 exactscale80Triplet749(U96 a,unsigned digit,const U96&n,const U96&u166,unsigned guard7){
 a=exactscale80Square749<false>(a,0,n,u166,guard7);a=exactscale80Square749<false>(a,0,n,u166,guard7);return exactscale80Square749<true>(a,digit,n,u166,guard7);
}
PGN_LAZY_HD U96 exactscale80Residue749(uint64_t low,uint32_t high,const U128&paid,const U96&rem){
 if(high!=54210u)return U96{};
 const U96 n{{uint32_t(low),uint32_t(low>>32),54210u}};
 U96 a=radix80Seed(211,n,paid,rem); // SAME validated168 seed, never the failed166 seed.
 const U96 u166{{(paid.w[0]>>2)|(paid.w[1]<<30),(paid.w[1]>>2)|(paid.w[2]<<30),paid.w[2]>>2}};
 const auto wide=radix80ShiftSeed(rem,5);U96 lifted{{wide.w[0],wide.w[1],wide.w[2]}};
 const unsigned lower=lifted.w[2]/54211u;
 pgn_coach173::sub(lifted,radix80Low96(U96{{lower,0,0}},n));
 const unsigned guard5=lower+unsigned(pgn_coach173::ge(lifted,n));
 const unsigned guard7=((paid.w[0]&3u)<<5)|guard5;
 for(int at=5;at>=0;at-=3)a=exactscale80Triplet749(a,(high>>at)&7u,n,u166,guard7);
 a=exactscale80Triplet749(a,((high&3u)<<1)|(n.w[1]>>31),n,u166,guard7);
 for(int at=28;at>=0;at-=3)a=exactscale80Triplet749(a,(n.w[1]>>at)&7u,n,u166,guard7);
 a=exactscale80Triplet749(a,((n.w[1]&1u)<<2)|(n.w[0]>>30),n,u166,guard7);
 for(int at=27;at>=1;at-=3)a=exactscale80Triplet749(a,(n.w[0]>>at)&7u,n,u166,guard7);
 a=exactscale80Square749<false>(a,0,n,u166,guard7);a=exactscale80Square749<true>(a,(n.w[0]>>1)&3u,n,u166,guard7);
 if(pgn_coach173::ge(a,n))pgn_coach173::sub(a,n);return a;
}
