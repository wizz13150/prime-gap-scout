#pragma once
#include <stdint.h>
#include <math.h>
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
namespace pgn_barrett70_base {
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
B70_HD U96 reciprocal160(const U96&n){
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
 return q;
}
B70_HD U96 squareLazy(const U96&a,const U96&n,const U96&u){
 // a<12n, n.high=10. Exact five-word square; column sums fit64bits.
 const uint64_t p00=uint64_t(a.w[0])*a.w[0],p01=uint64_t(a.w[0])*a.w[1];
 const uint64_t p02=uint64_t(a.w[0])*a.w[2],p11=uint64_t(a.w[1])*a.w[1];
 const uint64_t p12=uint64_t(a.w[1])*a.w[2],p22=uint64_t(a.w[2])*a.w[2];
 const uint32_t a0=uint32_t(p00);uint64_t s=(p00>>32)+2ULL*uint32_t(p01);const uint32_t a1=uint32_t(s);
 s=(s>>32)+2ULL*(p01>>32)+2ULL*uint32_t(p02)+uint32_t(p11);const uint32_t a2=uint32_t(s);
 s=(s>>32)+2ULL*(p02>>32)+(p11>>32)+2ULL*uint32_t(p12);const uint32_t a3=uint32_t(s);
 s=(s>>32)+2ULL*(p12>>32)+p22;const uint32_t a4=uint32_t(s);
 // x=floor(a²/2^64), u=floor(2^160/n). Drop only the low three
 // columns of x*u. Their omitted carry is in[0,4], always downward.
 const uint64_t s3=uint64_t(a4)*u.w[1]+uint64_t(a3)*u.w[2]
   +(uint64_t(a4)*u.w[0]>>32)+(uint64_t(a2)*u.w[2]>>32)+(uint64_t(a3)*u.w[1]>>32);
 const uint64_t s4=(s3>>32)+uint64_t(a4)*u.w[2];
 const U96 q{{uint32_t(s3),uint32_t(s4),uint32_t(s4>>32)}};
 const uint64_t n00=uint64_t(q.w[0])*n.w[0];
 // Use split32bit low products to retain the65th bit of column1.
 uint64_t c=(n00>>32)+uint32_t(uint64_t(q.w[0])*n.w[1])+uint32_t(uint64_t(q.w[1])*n.w[0]);
 const uint32_t prod1=uint32_t(c);
 const uint32_t prod2=uint32_t((c>>32)+(uint64_t(q.w[0])*n.w[1]>>32)+(uint64_t(q.w[1])*n.w[0]>>32)
   +uint64_t(q.w[0])*10u+uint64_t(q.w[1])*n.w[1]+uint64_t(q.w[2])*n.w[0]);
 U96 result{{a0,a1,a2}};sub(result,U96{{uint32_t(n00),prod1,prod2}});
 // q<=floor(a²/n), discrepancy<=5: 0<=result<6n<2^96.
 return result;
}
B70_HD U96 twice(const U96&a){return U96{{a.w[0]<<1,(a.w[1]<<1)|(a.w[0]>>31),(a.w[2]<<1)|(a.w[1]>>31)}};}
B70_HD bool test(uint64_t low){
 if(!(low&1))return false;
 const U96 n{{uint32_t(low),uint32_t(low>>32),10}},u=reciprocal160(n);
 // The exponent's first six bits are40..43. The initial ordinary residue
 // 2^(40+(low>>62)) is exact and below n;61squares then suffice.
 const uint64_t seed=1ULL<<(40+(low>>62));U96 a{{uint32_t(seed),uint32_t(seed>>32),0}};
 const uint64_t e=(low-1)>>1;
 for(int bit=60;bit>=0;--bit){a=squareLazy(a,n,u);if((e>>bit)&1)a=twice(a);}
 while(ge(a,n))sub(a,n);
 U96 expected{{1,0,0}};if(((low>>1)^(low>>2))&1){expected=n;sub(expected,U96{{1,0,0}});}
 return a.w[0]==expected.w[0]&&a.w[1]==expected.w[1]&&a.w[2]==expected.w[2];
}
}
#undef B70_HD
#undef B70_UNROLL
