#pragma once
#include <stdint.h>
#include <math.h>
#include "barrett70-exact.cuh"
#ifdef __CUDACC__
#define B70_HD __host__ __device__ __forceinline__
#define B70_UNROLL _Pragma("unroll")
#else
#define B70_HD inline
#define B70_UNROLL
#endif
// Independently constructed fixed-high10 Barrett experiment. The truncated
// high-product mechanism is documented in primesearch/mfaktc's Barrett code;
// no source code has been copied. Only integer corrections decide a residue.
namespace pgn_retained286_domains {
struct U96 {uint32_t w[3];};
struct U192 {uint32_t w[6];};
B70_HD bool ge(const U96&a,const U96&b){for(int i=2;i>=0;--i)if(a.w[i]!=b.w[i])return a.w[i]>b.w[i];return true;}
B70_HD uint32_t sub(U96&a,const U96&b){
#ifdef __CUDA_ARCH__
 uint32_t x,y,z,borrow;
 asm volatile("{\n\t.reg .u32 t0,t1,t2,c;\n\t"
  "sub.cc.u32 t0,%4,%7;\n\tsubc.cc.u32 t1,%5,%8;\n\t"
  "subc.cc.u32 t2,%6,%9;\n\tsubc.u32 c,0,0;\n\t"
  "mov.u32 %0,t0;\n\tmov.u32 %1,t1;\n\tmov.u32 %2,t2;\n\tmov.u32 %3,c;\n\t}"
  :"=r"(x),"=r"(y),"=r"(z),"=r"(borrow)
  :"r"(a.w[0]),"r"(a.w[1]),"r"(a.w[2]),"r"(b.w[0]),"r"(b.w[1]),"r"(b.w[2]));
 a=U96{{x,y,z}};return borrow&1u;
#else
 uint32_t c=0;B70_UNROLL for(int i=0;i<3;++i){uint64_t d=uint64_t(a.w[i])-b.w[i]-c;a.w[i]=uint32_t(d);c=uint32_t(d>>63);}return c;
#endif
}
B70_HD bool ge192(const U192&a,const U192&b){for(int i=5;i>=0;--i)if(a.w[i]!=b.w[i])return a.w[i]>b.w[i];return true;}
B70_HD uint32_t sub192(U192&a,const U192&b){uint32_t c=0;B70_UNROLL for(int i=0;i<6;++i){uint64_t d=uint64_t(a.w[i])-b.w[i]-c;a.w[i]=uint32_t(d);c=uint32_t(d>>63);}return c;}
B70_HD uint32_t add192(U192&a,const U192&b){uint64_t c=0;B70_UNROLL for(int i=0;i<6;++i){uint64_t s=uint64_t(a.w[i])+b.w[i]+c;a.w[i]=uint32_t(s);c=s>>32;}return uint32_t(c);}
B70_HD U192 shifted(const U96&n,unsigned bits){U192 r{};const unsigned words=bits/32,part=bits%32;B70_UNROLL for(unsigned i=0;i<3;++i){r.w[i+words]|=n.w[i]<<part;if(part)r.w[i+words+1]|=n.w[i]>>(32-part);}return r;}
B70_HD U192 timesDigit(const U192&a,uint32_t digit){U192 r{};uint64_t c=0;B70_UNROLL for(int i=0;i<6;++i){uint64_t p=uint64_t(a.w[i])*digit+c;r.w[i]=uint32_t(p);c=p>>32;}return r;}
B70_HD U96 reciprocal160(const U96&n,U96* remainder=nullptr,float* reciprocalHintOut=nullptr){
 // Six radix2^16 quotient digits. A float hint avoids a bit-at-a-time divide;
 // signed exact subtraction and correction close every digit independently.
 // Before each step: 0<=remainder<n*2^(shift+16). No shifted product
 // exceeds192bits; the largest first product is below2^164.
 U192 rem{{0,0,0,0,0,1}};U96 q{};
 const float denominator=float(n.w[2])*4294967296.0f+float(n.w[1])+float(n.w[0])*0x1p-32f;
 // rem<n*2^(shift+16), so its two highest possible words suffice
 // for a quotient HINT. All discarded words are still retained in the exact
 // six-word integer remainder and correction. No float decides acceptance.
 const float reciprocalHint=1.0f/denominator;
 if(reciprocalHintOut)*reciprocalHintOut=reciprocalHint;
 B70_UNROLL for(int k=5;k>=0;--k){
  const unsigned shift=unsigned(k)*16;const int topWord=(16*k+83)/32;
  const float highScale=(k&1)?281474976710656.0f:4294967296.0f;
  const float lowScale=(k&1)?65536.0f:1.0f;
  const float estimate=float(rem.w[topWord])*highScale+float(rem.w[topWord-1])*lowScale;
  const float hint=estimate*reciprocalHint;
  uint32_t digit=hint>=65535.0f?65535u:hint>0?uint32_t(hint):0u;
  const U192 unit=shifted(n,shift);const auto product=timesDigit(unit,digit);
  int top=-int(sub192(rem,product));
  while(top<0){top+=int(add192(rem,unit));--digit;}
  while(ge192(rem,unit)){sub192(rem,unit);++digit;}
  q.w[k/2]|=digit<<((k%2)*16);
 }
 if(remainder)*remainder=U96{{rem.w[0],rem.w[1],rem.w[2]}};
 return q;
}
// Preserve the original modulo2^64 column sums exactly. MAD.WIDE is
// documented also by NVIDIA's cuRAND umad helper; speed is NOT implied.
B70_HD uint64_t fusedWide(uint32_t a,uint32_t b,uint64_t c){
#ifdef __CUDA_ARCH__
 uint64_t out;asm("mad.wide.u32 %0,%1,%2,%3;":"=l"(out):"r"(a),"r"(b),"l"(c));return out;
#else
 return uint64_t(a)*b+c;
#endif
}
B70_HD uint32_t high32(uint32_t a,uint32_t b){
#ifdef __CUDA_ARCH__
 return __umulhi(a,b);
#else
 return uint32_t(uint64_t(a)*b>>32);
#endif
}
B70_HD U96 reduceSquaredWords(uint32_t a0,uint32_t a1,uint32_t a2,uint32_t a3,uint32_t a4,const U96&n,const U96&u){
 const uint64_t h=uint64_t(high32(a4,u.w[0]))+high32(a2,u.w[2])+high32(a3,u.w[1]);
 const uint64_t s3=fusedWide(a4,u.w[1],fusedWide(a3,u.w[2],h));
 const uint64_t s4=fusedWide(a4,u.w[2],s3>>32);
 const uint32_t q0=uint32_t(s3),q1=uint32_t(s4),q2=uint32_t(s4>>32);
 const uint64_t prod0=fusedWide(q0,n.w[0],0);
 const uint64_t prod12=fusedWide(q1,n.w[0],fusedWide(q0,n.w[1],prod0>>32));
 const uint32_t prod2=uint32_t(prod12>>32)+q0*n.w[2]+q1*n.w[1]+q2*n.w[0];
 U96 out{{a0,a1,a2}};sub(out,U96{{uint32_t(prod0),uint32_t(prod12),prod2}});return out;
}
B70_HD U96 squareLazy(const U96&a,const U96&n,const U96&u){
 // a<768n, n.high=8. Exact five-word square; column sums fit64bits.
#ifdef __CUDA_ARCH__
 uint32_t a0,a1,a2,a3,a4;
 // C = a0*a1 + B*a0*a2 + B^2*a1*a2, B=2^32.
 // Form 2*C once, then add the three diagonal products in one carry chain.
 // All five output limbs are exact for input<2^80 (in particular a<12*n).
 // No 64-bit column sums, branch or floating approximation is introduced.
 asm volatile("{\n\t"
  ".reg .u64 p00,p01,p02,p11,p12;\n\t"
  ".reg .u32 l00,h00,l01,h01,l02,h02,l11,h11,l12,h12,z;\n\t"
  ".reg .u32 c2,c3,c4,d1,d2,d3,d4,r1,r2,r3,r4;\n\t"
  "mul.wide.u32 p00,%5,%5;\n\tmul.wide.u32 p01,%5,%6;\n\t"
  "mul.wide.u32 p02,%5,%7;\n\tmul.wide.u32 p11,%6,%6;\n\t"
  "mul.wide.u32 p12,%6,%7;\n\tmul.lo.u32 z,%7,%7;\n\t"
  "mov.b64 {l00,h00},p00;\n\tmov.b64 {l01,h01},p01;\n\t"
  "mov.b64 {l02,h02},p02;\n\tmov.b64 {l11,h11},p11;\n\t"
  "mov.b64 {l12,h12},p12;\n\t"
  "add.cc.u32 c2,h01,l02;\n\taddc.cc.u32 c3,h02,l12;\n\taddc.u32 c4,h12,0;\n\t"
  "shl.b32 d1,l01,1;\n\tshf.l.wrap.b32 d2,l01,c2,1;\n\t"
  "shf.l.wrap.b32 d3,c2,c3,1;\n\tshf.l.wrap.b32 d4,c3,c4,1;\n\t"
  "add.cc.u32 r1,d1,h00;\n\taddc.cc.u32 r2,d2,l11;\n\t"
  "addc.cc.u32 r3,d3,h11;\n\taddc.u32 r4,d4,z;\n\t"
  "mov.u32 %0,l00;\n\tmov.u32 %1,r1;\n\tmov.u32 %2,r2;\n\t"
  "mov.u32 %3,r3;\n\tmov.u32 %4,r4;\n\t}"
  :"=r"(a0),"=r"(a1),"=r"(a2),"=r"(a3),"=r"(a4)
  :"r"(a.w[0]),"r"(a.w[1]),"r"(a.w[2]));
#else
 const uint64_t p00=uint64_t(a.w[0])*a.w[0],p01=uint64_t(a.w[0])*a.w[1];
 const uint64_t p02=uint64_t(a.w[0])*a.w[2],p11=uint64_t(a.w[1])*a.w[1];
 const uint64_t p12=uint64_t(a.w[1])*a.w[2],p22=uint64_t(a.w[2])*a.w[2];
 const uint32_t a0=uint32_t(p00);uint64_t s=(p00>>32)+2ULL*uint32_t(p01);const uint32_t a1=uint32_t(s);
 s=(s>>32)+2ULL*(p01>>32)+2ULL*uint32_t(p02)+uint32_t(p11);const uint32_t a2=uint32_t(s);
 s=(s>>32)+2ULL*(p02>>32)+(p11>>32)+2ULL*uint32_t(p12);const uint32_t a3=uint32_t(s);
 s=(s>>32)+2ULL*(p12>>32)+p22;const uint32_t a4=uint32_t(s);
#endif
 return reduceSquaredWords(a0,a1,a2,a3,a4,n,u);
}
B70_HD U96 twice(const U96&a){return U96{{a.w[0]<<1,(a.w[1]<<1)|(a.w[0]>>31),(a.w[2]<<1)|(a.w[1]>>31)}};}

B70_HD U96 shiftSmall(const U96&a,unsigned digit){
#ifdef __CUDA_ARCH__
 uint32_t x,y,z;
 asm volatile("{.reg .u32 t0,t1,t2;\n\tshl.b32 t0,%3,%6;\n\tshf.l.wrap.b32 t1,%3,%4,%6;\n\tshf.l.wrap.b32 t2,%4,%5,%6;\n\tmov.u32 %0,t0;\n\tmov.u32 %1,t1;\n\tmov.u32 %2,t2;}"
  :"=r"(x),"=r"(y),"=r"(z):"r"(a.w[0]),"r"(a.w[1]),"r"(a.w[2]),"r"(digit));
 return U96{{x,y,z}};
#else
 if(!digit)return a;
 return U96{{a.w[0]<<digit,(a.w[1]<<digit)|(a.w[0]>>(32-digit)),(a.w[2]<<digit)|(a.w[1]>>(32-digit))}};
#endif
}

// B=2^64,10B<=n<11B,0<=a<12n. q0=floor(a.high/11) differs
// from floor(a/n) by0or1: h>=10q andq<=11. Thus exactone repair.
B70_HD U96 normalizeFinal12(U96 a,const U96&n){
 const uint32_t q=a.w[2]/(n.w[2]+1u);
 uint64_t product=uint64_t(n.w[0])*q;U96 multiple{{uint32_t(product),0,0}};
 product=uint64_t(n.w[1])*q+(product>>32);multiple.w[1]=uint32_t(product);
 multiple.w[2]=n.w[2]*q+uint32_t(product>>32);
 sub(a,multiple);if(ge(a,n))sub(a,n);if(ge(a,n))sub(a,n);return a;
}

// Exact seed2^128 from the already certified quotient u160:
// floor(floor(2^160/n)/2^32)=floor(2^128/n). n.high=8.
B70_HD U96 seedPower128(const U96&n,const U96&u){
 const uint64_t q=(uint64_t(u.w[2])<<32)|u.w[1];
 const uint64_t low=(uint64_t(n.w[1])<<32)|n.w[0];
 const uint64_t pl=low*q;
#ifdef __CUDA_ARCH__
 const uint64_t ph=__umul64hi(low,q)+n.w[2]*q;
#else
 const uint64_t a0=uint32_t(low),a1=low>>32,b0=uint32_t(q),b1=q>>32;
 const uint64_t p0=a0*b0,t=a1*b0+(p0>>32),mid=uint32_t(t)+a0*b1;
 const uint64_t ph=a1*b1+(t>>32)+(mid>>32)+n.w[2]*q;
#endif
 const uint64_t rl=0-pl,rh=0-ph-uint64_t(pl!=0);
 return U96{{uint32_t(rl),uint32_t(rl>>32),uint32_t(rh)}};
}

B70_HD unsigned exponentBit(uint64_t lo,uint32_t hi,int bit){return bit>=64?unsigned((hi>>(bit-64))&1u):unsigned((lo>>bit)&1u);}
B70_HD U96 shiftReduced(U96 a,unsigned amount,const U96&n,const U96&u){
 while(amount){const unsigned d=amount>=32?32:amount;U96 r;
  if(d==32)r=reduceSquaredWords(0,a.w[0],a.w[1],a.w[2],0,n,u);
  else r=reduceSquaredWords(a.w[0]<<d,(a.w[1]<<d)|(a.w[0]>>(32-d)),(a.w[2]<<d)|(a.w[1]>>(32-d)),a.w[2]>>(32-d),0,n,u);
  a=normalizeFinal12(r,n);amount-=d;
 }return a;
}
B70_HD U96 seedPrefix(const U96&n,const U96&u,const U96&rem,unsigned prefix){
 U96 a=seedPower128(n,u);
 if(prefix==255){
  a=normalizeFinal12(squareLazy(a,n,u),n);
  if(a.w[0]&1){uint64_t c=0;for(int i=0;i<3;++i){uint64_t z=uint64_t(a.w[i])+n.w[i]+c;a.w[i]=uint32_t(z);c=z>>32;}}
  return U96{{(a.w[0]>>1)|(a.w[1]<<31),(a.w[1]>>1)|(a.w[2]<<31),a.w[2]>>1}};
 }
 return prefix>=160?shiftReduced(rem,prefix-160,n,u):shiftReduced(a,prefix-128,n,u);
}
B70_HD bool testWithReciprocal(uint64_t low,uint32_t high,const U96&u,const U96&rem,float){
 if(!(low&1)||high<8||high>16383)return false;
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};
 const uint64_t elo=((low-1)>>1)|(uint64_t(high&1)<<63);const uint32_t ehi=high>>1;
 unsigned highBits=0;for(uint32_t t=high;t;t>>=1)++highBits;
 const int exponentLength=int(63+highBits),remaining=exponentLength-8;
 unsigned prefix=0;for(int bit=exponentLength-1;bit>=remaining;--bit)prefix=(prefix<<1)|exponentBit(elo,ehi,bit);
 U96 a=seedPrefix(n,u,rem,prefix);
 const unsigned width=high<=63?3:high<=1023?2:high<=4095?1:0;
 if(!width){
  for(int bit=remaining-1;bit>=1;--bit){a=normalizeFinal12(squareLazy(a,n,u),n);if(exponentBit(elo,ehi,bit))a=twice(a);}
 }else{
  int bit=remaining-1;
  while(bit>=1){const unsigned count=unsigned(bit)<width?unsigned(bit):width;unsigned digit=0;
   for(unsigned j=0;j<count;++j,--bit){a=squareLazy(a,n,u);digit=(digit<<1)|exponentBit(elo,ehi,bit);}
   a=shiftSmall(a,digit);
  }
 }
 a=squareLazy(a,n,u);if(elo&1)a=twice(a);a=normalizeFinal12(a,n);
 U96 expected{{1,0,0}};if(((low>>1)^(low>>2))&1){expected=n;sub(expected,U96{{1,0,0}});}
 return a.w[0]==expected.w[0]&&a.w[1]==expected.w[1]&&a.w[2]==expected.w[2];
}
B70_HD bool test(uint64_t low,uint32_t high){
 if(!(low&1)||high<8||high>16383)return false;
 const U96 n{{uint32_t(low),uint32_t(low>>32),high}};U96 rem{};float hint=0;const U96 u=reciprocal160(n,&rem,&hint);
 return testWithReciprocal(low,high,u,rem,hint);
}

}
#undef B70_HD
#undef B70_UNROLL
