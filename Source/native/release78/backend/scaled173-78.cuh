#pragma once
#include <stdint.h>
#ifdef __CUDACC__
#define S173_HD __host__ __device__ __forceinline__
#else
#define S173_HD inline
#endif
namespace pgn_coach173 {
struct U96 { uint32_t w[3]; };
struct U128 { uint32_t w[4]; };
struct U192 { uint32_t w[6]; };
enum class MathStatus : uint32_t { NeedsExactFallback=0, LazyResidue=1 };
S173_HD bool ge(const U96&a,const U96&b) {
  if(a.w[2]!=b.w[2])return a.w[2]>b.w[2];
  if(a.w[1]!=b.w[1])return a.w[1]>b.w[1];
  return a.w[0]>=b.w[0];
}
S173_HD void sub(U96&a,const U96&b) {
#ifdef __CUDA_ARCH__
 uint32_t x,y,z;
 asm volatile("{.reg .u32 t0,t1,t2;\n\t"
  "sub.cc.u32 t0,%3,%6;\n\tsubc.cc.u32 t1,%4,%7;\n\t"
  "subc.u32 t2,%5,%8;\n\t"
  "mov.u32 %0,t0;\n\tmov.u32 %1,t1;\n\tmov.u32 %2,t2;\n\t}"
  :"=r"(x),"=r"(y),"=r"(z)
  :"r"(a.w[0]),"r"(a.w[1]),"r"(a.w[2]),"r"(b.w[0]),"r"(b.w[1]),"r"(b.w[2]));
 a=U96{{x,y,z}};
#else

  uint64_t t=uint64_t(a.w[0])-b.w[0];a.w[0]=uint32_t(t);
  t=uint64_t(a.w[1])-b.w[1]-(t>>63);a.w[1]=uint32_t(t);
  t=uint64_t(a.w[2])-b.w[2]-(t>>63);a.w[2]=uint32_t(t);

#endif
}
S173_HD U96 twice(const U96&a) {
  return U96{{a.w[0]<<1,(a.w[1]<<1)|(a.w[0]>>31),(a.w[2]<<1)|(a.w[1]>>31)}};
}
S173_HD U192 square6(const U96&a) {
#ifdef __CUDA_ARCH__
 U192 out{};

 asm volatile("{\n\t"
  ".reg .u64 p00,p01,p02,p11,p12,p22;\n\t"
  ".reg .u32 l00,h00,l01,h01,l02,h02,l11,h11,l12,h12,l22,h22;\n\t"
  ".reg .u32 c2,c3,c4,d1,d2,d3,d4,d5,r1,r2,r3,r4,r5;\n\t"
  "mul.wide.u32 p00,%6,%6;\n\tmul.wide.u32 p01,%6,%7;\n\t"
  "mul.wide.u32 p02,%6,%8;\n\tmul.wide.u32 p11,%7,%7;\n\t"
  "mul.wide.u32 p12,%7,%8;\n\tmul.wide.u32 p22,%8,%8;\n\t"
  "mov.b64 {l00,h00},p00;\n\tmov.b64 {l01,h01},p01;\n\t"
  "mov.b64 {l02,h02},p02;\n\tmov.b64 {l11,h11},p11;\n\t"
  "mov.b64 {l12,h12},p12;\n\tmov.b64 {l22,h22},p22;\n\t"
  "add.cc.u32 c2,h01,l02;\n\taddc.cc.u32 c3,h02,l12;\n\taddc.u32 c4,h12,0;\n\t"
  "shl.b32 d1,l01,1;\n\tshf.l.wrap.b32 d2,l01,c2,1;\n\t"
  "shf.l.wrap.b32 d3,c2,c3,1;\n\tshf.l.wrap.b32 d4,c3,c4,1;\n\tshr.u32 d5,c4,31;\n\t"
  "add.cc.u32 r1,d1,h00;\n\taddc.cc.u32 r2,d2,l11;\n\t"
  "addc.cc.u32 r3,d3,h11;\n\taddc.cc.u32 r4,d4,l22;\n\taddc.u32 r5,d5,h22;\n\t"
  "mov.u32 %0,l00;\n\tmov.u32 %1,r1;\n\tmov.u32 %2,r2;\n\t"
  "mov.u32 %3,r3;\n\tmov.u32 %4,r4;\n\tmov.u32 %5,r5;\n\t}"
  :"=r"(out.w[0]),"=r"(out.w[1]),"=r"(out.w[2]),"=r"(out.w[3]),"=r"(out.w[4]),"=r"(out.w[5])
  :"r"(a.w[0]),"r"(a.w[1]),"r"(a.w[2]));

 return out;
#else

  const uint64_t p00=uint64_t(a.w[0])*a.w[0],p01=uint64_t(a.w[0])*a.w[1];
  const uint64_t p02=uint64_t(a.w[0])*a.w[2],p11=uint64_t(a.w[1])*a.w[1];
  const uint64_t p12=uint64_t(a.w[1])*a.w[2],p22=uint64_t(a.w[2])*a.w[2];
  U192 x{};x.w[0]=uint32_t(p00);
  uint64_t s=(p00>>32)+2ULL*uint32_t(p01);x.w[1]=uint32_t(s);
  s=(s>>32)+2ULL*(p01>>32)+2ULL*uint32_t(p02)+uint32_t(p11);x.w[2]=uint32_t(s);
  s=(s>>32)+2ULL*(p02>>32)+(p11>>32)+2ULL*uint32_t(p12);x.w[3]=uint32_t(s);
  s=(s>>32)+2ULL*(p12>>32)+uint32_t(p22);x.w[4]=uint32_t(s);
  x.w[5]=uint32_t((p22>>32)+(s>>32));return x;

#endif
}
S173_HD U192 square5Known(const U96&a){
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

 return U192{{a0,a1,a2,a3,a4,0}};
#else
 U192 x=square6(a);x.w[5]=0;return x;
#endif
}
S173_HD U128 highBand9(const U192&x,const U96&u) {
#ifdef __CUDA_ARCH__
 U128 out{};
 asm volatile("{\n\t.reg .u32 a0,a1,a2,a3,t;\n\t"
  "mul.hi.u32 a0,%6,%8;\n\t"
  "mul.hi.u32 t,%4,%10;\n\t"
  "add.cc.u32 a0,a0,t;\n\t"
  "addc.u32 a1,0,0;\n\t"
  "mul.hi.u32 t,%5,%9;\n\t"
  "add.cc.u32 a0,a0,t;\n\t"
  "addc.u32 a1,a1,0;\n\t"
  "mov.u32 a2,0;\n\t"
  "mov.u32 a3,0;\n\t"
  "mad.lo.cc.u32 a0,%5,%10,a0;\n\t"
  "madc.hi.cc.u32 a1,%5,%10,a1;\n\t"
  "addc.cc.u32 a2,a2,0;\n\t"
  "addc.u32 a3,a3,0;\n\t"
  "mad.lo.cc.u32 a0,%6,%9,a0;\n\t"
  "madc.hi.cc.u32 a1,%6,%9,a1;\n\t"
  "addc.cc.u32 a2,a2,0;\n\t"
  "addc.u32 a3,a3,0;\n\t"
  "mad.lo.cc.u32 a0,%7,%8,a0;\n\t"
  "madc.hi.cc.u32 a1,%7,%8,a1;\n\t"
  "addc.cc.u32 a2,a2,0;\n\t"
  "addc.u32 a3,a3,0;\n\t"
  "mad.lo.cc.u32 a1,%6,%10,a1;\n\t"
  "madc.hi.cc.u32 a2,%6,%10,a2;\n\t"
  "addc.u32 a3,a3,0;\n\t"
  "mad.lo.cc.u32 a1,%7,%9,a1;\n\t"
  "madc.hi.cc.u32 a2,%7,%9,a2;\n\t"
  "addc.u32 a3,a3,0;\n\t"
  "mad.lo.cc.u32 a2,%7,%10,a2;\n\t"
  "madc.hi.cc.u32 a3,%7,%10,a3;\n\t"
  "mov.u32 %0,a0;\n\t"
  "mov.u32 %1,a1;\n\t"
  "mov.u32 %2,a2;\n\t"
  "mov.u32 %3,a3;\n\t"
  "}"
  :"=r"(out.w[0]),"=r"(out.w[1]),"=r"(out.w[2]),"=r"(out.w[3])
  :"r"(x.w[2]),"r"(x.w[3]),"r"(x.w[4]),"r"(x.w[5]),"r"(u.w[0]),"r"(u.w[1]),"r"(u.w[2]));
 return out;
#else

  const uint64_t h=(uint64_t(x.w[4])*u.w[0]>>32)
      +(uint64_t(x.w[2])*u.w[2]>>32)+(uint64_t(x.w[3])*u.w[1]>>32);
  const uint64_t p30=uint64_t(x.w[3])*u.w[2],p31=uint64_t(x.w[4])*u.w[1],p32=uint64_t(x.w[5])*u.w[0];
  const uint64_t p40=uint64_t(x.w[4])*u.w[2],p41=uint64_t(x.w[5])*u.w[1],p50=uint64_t(x.w[5])*u.w[2];
  U128 a{};uint64_t s=h+uint32_t(p30)+uint32_t(p31)+uint32_t(p32);a.w[0]=uint32_t(s);
  s=(s>>32)+(p30>>32)+(p31>>32)+(p32>>32)+uint32_t(p40)+uint32_t(p41);a.w[1]=uint32_t(s);
  s=(s>>32)+(p40>>32)+(p41>>32)+uint32_t(p50);a.w[2]=uint32_t(s);
  a.w[3]=uint32_t((s>>32)+(p50>>32));return a;

#endif
}
S173_HD U96 productLow96(const U96&q,const U96&n) {
  const uint64_t p00=uint64_t(q.w[0])*n.w[0],p01=uint64_t(q.w[0])*n.w[1],p10=uint64_t(q.w[1])*n.w[0];
  U96 r{{uint32_t(p00),0,0}};
  uint64_t s=(p00>>32)+uint32_t(p01)+uint32_t(p10);r.w[1]=uint32_t(s);
  s=(s>>32)+(p01>>32)+(p10>>32)+uint32_t(uint64_t(q.w[0])*n.w[2])
      +uint32_t(uint64_t(q.w[1])*n.w[1])+uint32_t(uint64_t(q.w[2])*n.w[0]);
  r.w[2]=uint32_t(s);return r;
}
class Context {
  U96 n_{},u_{};
public:
  // Diagnostic safe constructor, not a free production cache adapter.
  // The exact U160 certificate costs nine products here.
  S173_HD static MathStatus fromChecked160(const U96&n,const U96&u160,Context&out,U96*rem160=nullptr) {
    if(!(n.w[0]&1u)||n.w[2]<8192u||n.w[2]>=16384u)return MathStatus::NeedsExactFallback;
    U192 p{};
    for(unsigned i=0;i<3;++i){uint64_t carry=0;for(unsigned j=0;j<3;++j){
      const uint64_t t=uint64_t(n.w[i])*u160.w[j]+p.w[i+j]+carry;p.w[i+j]=uint32_t(t);carry=t>>32;
    }p.w[i+3]=uint32_t(carry);}
    U192 difference{};uint32_t borrow=0;
    for(unsigned i=0;i<6;++i){const uint64_t t=uint64_t(i==5?1u:0u)-p.w[i]-borrow;difference.w[i]=uint32_t(t);borrow=uint32_t(t>>63);}
    if(borrow||difference.w[3]||difference.w[4]||difference.w[5])return MathStatus::NeedsExactFallback;
    U96 r{{difference.w[0],difference.w[1],difference.w[2]}};
    if(ge(r,n))return MathStatus::NeedsExactFallback;
    if(rem160)*rem160=r;
    U96 u=u160;
    for(unsigned bit=0;bit<13;++bit){
      if(u.w[2]&0x80000000u)return MathStatus::NeedsExactFallback;
      u=twice(u);r=twice(r);if(ge(r,n)){sub(r,n);u.w[0]|=1u;}
    }
    Context fresh;fresh.n_=n;fresh.u_=u;out=fresh;return MathStatus::LazyResidue;
  }
  S173_HD MathStatus squareFor(const U96&actualN,const U96&a,U96&out) const {
    if(!u_.w[2]||actualN.w[0]!=n_.w[0]||actualN.w[1]!=n_.w[1]||actualN.w[2]!=n_.w[2])return MathStatus::NeedsExactFallback;
    const U96 limit{{n_.w[0]<<8,(n_.w[1]<<8)|(n_.w[0]>>24),(n_.w[2]<<8)|(n_.w[1]>>24)}};
    if(ge(a,limit))return MathStatus::NeedsExactFallback;
    const U192 x=square6(a);const U128 band=highBand9(x,u_);
    if(band.w[3]>>13)return MathStatus::NeedsExactFallback;
    const U96 q{{(band.w[0]>>13)|(band.w[1]<<19),(band.w[1]>>13)|(band.w[2]<<19),(band.w[2]>>13)|(band.w[3]<<19)}};
    U96 r{{x.w[0],x.w[1],x.w[2]}};sub(r,productLow96(q,n_));
    if(ge(r,twice(n_)))return MathStatus::NeedsExactFallback;
    out=r;return MathStatus::LazyResidue;
  }
};
static_assert(sizeof(U96)==12,"Exact three-word unsigned representation");
static_assert(sizeof(U192)==24,"Exact six-word square representation");
} // namespace pgn_coach173
#undef S173_HD
