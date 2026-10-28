#pragma once
PGN_LAZY_HD uint32_t radix80High32(uint32_t a,uint32_t b){
#ifdef __CUDA_ARCH__
 return __umulhi(a,b);
#else
 return uint32_t((uint64_t(a)*b)>>32);
#endif
}
PGN_LAZY_HD uint64_t radix80Mad64(uint32_t a,uint32_t b,uint64_t c){
#ifdef __CUDA_ARCH__
 uint64_t r;asm("mad.wide.u32 %0,%1,%2,%3;":"=l"(r):"r"(a),"r"(b),"l"(c));return r;
#else
 return uint64_t(a)*b+c;
#endif
}
PGN_LAZY_HD U96 radix80Low96(const U96&q,const U96&n){
 const uint64_t p0=radix80Mad64(q.w[0],n.w[0],0);
 const uint64_t p12=radix80Mad64(q.w[1],n.w[0],radix80Mad64(q.w[0],n.w[1],p0>>32));
 const uint32_t p2=uint32_t(p12>>32)+q.w[0]*n.w[2]+q.w[1]*n.w[1]+q.w[2]*n.w[0];
 return U96{{uint32_t(p0),uint32_t(p12),p2}};
}
PGN_LAZY_HD U96 radix80Column96(const U192&x,const U96&u){
 const uint64_t h=uint64_t(radix80High32(x.w[4],u.w[0]))+radix80High32(x.w[2],u.w[2])+radix80High32(x.w[3],u.w[1]);
 const uint64_t s3=radix80Mad64(x.w[4],u.w[1],radix80Mad64(x.w[3],u.w[2],h));
 const uint64_t s4=radix80Mad64(x.w[4],u.w[2],s3>>32);
 return U96{{uint32_t(s3),uint32_t(s4),uint32_t(s4>>32)}};
}

// Included inside pgn_fast_batch499 after P and before residue/test.
PGN_LAZY_HD U192 radix80ShiftSeed(const U96&a,unsigned bits){
 const unsigned w=bits/32,s=bits%32;
 const uint32_t a0=a.w[0]<<s,a1=(a.w[1]<<s)|(s?a.w[0]>>(32-s):0u),a2=(a.w[2]<<s)|(s?a.w[1]>>(32-s):0u),a3=s?a.w[2]>>(32-s):0u;
 if(w==0)return U192{{a0,a1,a2,a3,0,0}};if(w==1)return U192{{0,a0,a1,a2,a3,0}};return U192{{0,0,a0,a1,a2,a3}};
}
PGN_LAZY_HD U96 radix80Seed(unsigned prefix,const U96&n,const U128&u,const U96&rem){
 U192 x{};
 if(prefix>=168)x=radix80ShiftSeed(rem,prefix-168);
 else{
  const U96 q128{{(u.w[1]>>8)|(u.w[2]<<24),(u.w[2]>>8)|(u.w[3]<<24),u.w[3]>>8}};
  U96 r128{};pgn_coach173::sub(r128,radix80Low96(q128,n));x=radix80ShiftSeed(r128,prefix-128);
 }
 const auto q=pgn_fast_grouped_wide490::quotientLow96<168>(pgn_fast_grouped_wide490::highBand<3>(x,u));
 U96 r{{x.w[0],x.w[1],x.w[2]}};pgn_coach173::sub(r,radix80Low96(q,n));
 if(pgn_coach173::ge(r,n))pgn_coach173::sub(r,n);return r;
}
template<bool Fused,uint32_t FixedHigh>PGN_LAZY_HD U96 radix80Square(U96 a,unsigned digit,const U96&n,const U128&u){
 const auto x=pgn_coach173::square5Known(a);
 U96 reciprocal{{u.w[0],u.w[1],u.w[2]}};
 if constexpr(Fused){const auto v=pgn_fast_grouped_wide490::shift128(u,digit);reciprocal=U96{{v.w[0],v.w[1],v.w[2]}};}
 U96 z{};
 if constexpr(!Fused&&FixedHigh==54210u)z=radix80Column96(x,reciprocal);
 else z=pgn_fast_band96_518::highBand(x,reciprocal);
 const U96 q{{(z.w[0]>>8)|(z.w[1]<<24),(z.w[1]>>8)|(z.w[2]<<24),z.w[2]>>8}};
 U96 r{{x.w[0],x.w[1],x.w[2]}};
 if constexpr(Fused)r=pgn_fast_grouped_wide490::shiftLow96(x,digit);
 pgn_coach173::sub(r,radix80Low96(q,n));
 constexpr bool NarrowSafe=FixedHigh&&((uint64_t(FixedHigh)+1u)*263u<(1ull<<24));
 if constexpr(Fused||!NarrowSafe){
  if constexpr(FixedHigh==54210u){if(r.w[2]>=65024u)pgn_coach173::sub(r,n);}
  else if(r.w[2]&0x10000u)pgn_coach173::sub(r,n);
 }
 // Redundant but exact width information for the compiler: closure was proved
 // from raw<2N and the radix correction, not from silently truncating raw.
 r.w[2]&=0xffffu;return r;
}
template<uint32_t FixedHigh>PGN_LAZY_HD U96 radix80Triplet(U96 a,unsigned digit,const U96&n,const U128&u){
 return radix80Square<true,FixedHigh>(radix80Square<false,FixedHigh>(radix80Square<false,FixedHigh>(a,0,n,u),0,n,u),digit,n,u);
}
template<uint32_t FixedHigh>PGN_LAZY_HD U96 radix80Residue(uint64_t low,uint32_t high,const U128&u,const U96&rem){
 constexpr unsigned HBits=8,HRemain=2,HiConsumed=1,HiBits=31,HiRemain=1,LoConsumed=2,Tail=2;
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};U96 a=radix80Seed(high>>HBits,n,u,rem);
 for(int at=int(HBits)-3;at>=0;at-=3)a=radix80Triplet<FixedHigh>(a,(high>>at)&7u,n,u);
 a=radix80Triplet<FixedHigh>(a,((high&3u)<<1)|(n.w[1]>>31),n,u);
 for(int at=int(HiBits)-3;at>=0;at-=3)a=radix80Triplet<FixedHigh>(a,(n.w[1]>>at)&7u,n,u);
 a=radix80Triplet<FixedHigh>(a,((n.w[1]&1u)<<2)|(n.w[0]>>30),n,u);
 for(int at=29-int(LoConsumed);at>=1;at-=3)a=radix80Triplet<FixedHigh>(a,(n.w[0]>>at)&7u,n,u);
 a=radix80Square<false,FixedHigh>(a,0,n,u);
 a=radix80Square<true,FixedHigh>(a,(n.w[0]>>1)&3u,n,u);
 if(pgn_coach173::ge(a,n))pgn_coach173::sub(a,n);return a;
}
