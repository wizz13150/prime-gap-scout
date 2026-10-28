typedef unsigned int uint32_t;typedef unsigned long long uint64_t;typedef int int32_t;

// Private numeric component gate SOURCE, never a Native miner or benchmark.

// PRIVATE SOURCE integration only. NOT compiled/tested/Native qualified.
// Same State8 and perpoint API as the retained M565/C29 wrapper.

// M583 private SOURCE. Not compiled, numerically tested, or Native qualified.
// Real high64 word10 ONLY, exact old JobMu and a narrower <=2^36 job span.
// Parent C25/C29 and all accepted images remain unmodified.

// Independent SOURCE control candidate after exact Native AOT C28.
// No arithmetic primitive, C25 consumer, M564 tiny gate or Native kit changed.


// C20 experimental component. NO Native/GPU qualification.
// N=10*2^64+nlo odd. A<2N. muL=floor(2^96/Nmax) for a job
// whose actual query envelope obeys C19, hence 0<=2^96/N-muL<2.
// R64 encoded residues, NOT the parent's ordinary/Barrett representation.
namespace myr_r64lazy32 {
struct Value { uint32_t x, y, z; };

#if defined(__CUDACC__)
#define C20_DEV __device__ __forceinline__
#else
#define C20_DEV inline
#endif

C20_DEV uint32_t negative_inverse32(uint32_t n0) {
    uint32_t x = n0;  // odd n0: n0*x = 1 mod8
    x *= 2u - n0*x;
    x *= 2u - n0*x;
    x *= 2u - n0*x;
    x *= 2u - n0*x;   // 3*2^4 >=32 correct bits
    return 0u-x;
}

#if defined(__CUDA_ARCH__)
C20_DEV Value square(Value a, uint32_t n0, uint32_t n1,
                      uint32_t np32, uint32_t muL) {
    Value d;
    // One CC-local block. l/m/h are a column plus carry, not a 64-bit C++
    // comparison or carry materialisation. Small terms precede full products.
    asm volatile(
        "{\n\t"
        ".reg .u32 l,m,h,q0,q1,z2,t0,t1,t2,q,p0,p1,p2;\n\t"
        "add.u32 z2,%5,%5;\n\t"
        "mul.lo.u32 l,%3,%3;\n\t"
        "mul.hi.u32 m,%3,%3;\n\t"
        "mul.lo.u32 q0,l,%8;\n\t"
        "mad.lo.cc.u32 l,q0,%6,l;\n\t"
        "madc.hi.cc.u32 m,q0,%6,m;\n\t"
        "addc.u32 h,0,0;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q0,%7,l;\n\t"
        "madc.hi.u32 m,q0,%7,m;\n\t"
        "mov.u32 h,0;\n\t"
        "mad.lo.cc.u32 l,%3,%4,l;\n\t"
        "madc.hi.cc.u32 m,%3,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mad.lo.cc.u32 l,%3,%4,l;\n\t"
        "madc.hi.cc.u32 m,%3,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mul.lo.u32 q1,l,%8;\n\t"
        "mad.lo.cc.u32 l,q1,%6,l;\n\t"
        "madc.hi.cc.u32 m,q1,%6,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q0,10,l;\n\t"
        "madc.hi.u32 m,q0,10,m;\n\t"
        "mad.lo.cc.u32 l,%3,z2,l;\n\t"
        "madc.hi.u32 m,%3,z2,m;\n\t"
        "mov.u32 h,0;\n\t"
        "mad.lo.cc.u32 l,q1,%7,l;\n\t"
        "madc.hi.cc.u32 m,q1,%7,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mad.lo.cc.u32 l,%4,%4,l;\n\t"
        "madc.hi.cc.u32 m,%4,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mov.u32 t0,l;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q1,10,l;\n\t"
        "madc.hi.u32 m,q1,10,m;\n\t"
        "mad.lo.cc.u32 l,%4,z2,l;\n\t"
        "madc.hi.u32 m,%4,z2,m;\n\t"
        "mov.u32 t1,l;\n\t"
        "mad.lo.u32 t2,%5,%5,m;\n\t"
        "mul.hi.u32 q,t2,%9;\n\t"
        "mul.lo.u32 p0,q,%6;\n\t"
        "mul.hi.u32 p1,q,%6;\n\t"
        "mad.lo.cc.u32 p1,q,%7,p1;\n\t"
        "madc.hi.u32 p2,q,%7,0;\n\t"
        "mad.lo.u32 p2,q,10,p2;\n\t"
        "sub.cc.u32 %0,t0,p0;\n\t"
        "subc.cc.u32 %1,t1,p1;\n\t"
        "subc.u32 %2,t2,p2;\n\t"
        "}\n"
        : "=r"(d.x), "=r"(d.y), "=r"(d.z)
        : "r"(a.x), "r"(a.y), "r"(a.z), "r"(n0), "r"(n1),
          "r"(np32), "r"(muL));
    return d;
}
#endif

#undef C20_DEV
} // namespace myr_r64lazy32



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
namespace pgn_barrett70 {
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
 const uint32_t prod2=uint32_t(prod12>>32)+q0*10u+q1*n.w[1]+q2*n.w[0];
 U96 out{{a0,a1,a2}};sub(out,U96{{uint32_t(prod0),uint32_t(prod12),prod2}});return out;
}
B70_HD U96 squareLazy(const U96&a,const U96&n,const U96&u){
 // a<768n, n.high=10. Exact five-word square; column sums fit64bits.
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
 const uint32_t q=a.w[2]/11u;
 uint64_t product=uint64_t(n.w[0])*q;U96 multiple{{uint32_t(product),0,0}};
 product=uint64_t(n.w[1])*q+(product>>32);multiple.w[1]=uint32_t(product);
 multiple.w[2]=10u*q+uint32_t(product>>32);
 sub(a,multiple);if(ge(a,n))sub(a,n);return a;
}

B70_HD bool testWithReciprocal(uint64_t low,const U96&u,const U96&remainder,float reusedHint){
 if(!(low&1))return false;
 const U96 n{{uint32_t(low),uint32_t(low>>32),10}};
 // The exact R160 already exists at the end of reciprocal generation.
 // Shift0..15 implements the first8 exponent bits160..175, then repair
 // a float quotient hint by exact signed96bit arithmetic. No FP acceptance.
 U96 a=shiftSmall(remainder,unsigned(low>>60));
 // Reuse the already-paid inverse hint, in the SAME2^32 scaled units.
 // Dropping a.w0 affects only the hint: exact96-bit correction still decides.
 const float hint=(float(a.w[2])*4294967296.0f+float(a.w[1]))*reusedHint;const uint32_t quotient=hint>=32768.0f?32768u:hint>0?uint32_t(hint):0u;
 uint64_t product=uint64_t(n.w[0])*quotient;U96 multiple{{uint32_t(product),0,0}};
 product=uint64_t(n.w[1])*quotient+(product>>32);multiple.w[1]=uint32_t(product);multiple.w[2]=10u*quotient+uint32_t(product>>32);
 int sign=-int(sub(a,multiple));
 while(sign<0){uint64_t carry=0;B70_UNROLL for(int i=0;i<3;++i){const uint64_t v=uint64_t(a.w[i])+n.w[i]+carry;a.w[i]=uint32_t(v);carry=v>>32;}sign+=int(carry);}
 while(ge(a,n))sub(a,n);
 const uint64_t e=(low-1)>>1;a=squareLazy(a,n,u);if((e>>58)&1)a=twice(a);
 // After each group a<768*n<2^78. For this full u160 reciprocal,
 // 2^64/n + 768^2*121/2^32 <0.117<1. Together with the original
 // discarded carry<=4 this preserves squareLazy's exact output<6*n.
 // Fused square supports every input<2^80. No normalization between rounds.
 for(int bit=57;bit>=3;bit-=3){
  a=squareLazy(a,n,u);a=squareLazy(a,n,u);a=squareLazy(a,n,u);
  a=shiftSmall(a,unsigned((e>>(bit-2))&7));
 }
 // Nineteen groups consume bits57..1; final bit0 retains the old <12*n bound.
 a=squareLazy(a,n,u);if(e&1)a=twice(a);
 a=normalizeFinal12(a,n);
 U96 expected{{1,0,0}};if(((low>>1)^(low>>2))&1){expected=n;sub(expected,U96{{1,0,0}});}
 return a.w[0]==expected.w[0]&&a.w[1]==expected.w[1]&&a.w[2]==expected.w[2];
}
B70_HD bool test(uint64_t low){
 if(!(low&1))return false;
 float hint=0;U96 remainder{};const U96 n{{uint32_t(low),uint32_t(low>>32),10}};
 const U96 u=reciprocal160(n,&remainder,&hint);
 return testWithReciprocal(low,u,remainder,hint);
}
}
#undef B70_HD
#undef B70_UNROLL


// C21 component SOURCE, no full-consumer compile/GPU/Native qualification.
// C21 proof extends the UNCHANGED C20 implementation to input<256*N.
// Only the implicit-high10 parent domain is supported; not arbitrary 68bits.
namespace myr_r64lazy32_prp {
using myr_r64lazy32::Value;
#if defined(__CUDACC__)
#define C21_HD __host__ __device__ __forceinline__
#define C21_UNROLL _Pragma("unroll")
#else
#define C21_HD inline
#define C21_UNROLL
#endif

struct JobMu {
    uint64_t minLow, maxLow;
    uint32_t muLower, ready;
};
static constexpr uint32_t Ready = 0xC21A5AFEu;

// q*N versus2^96, exact4-word comparison, no __int128 dependency.
C21_HD int compareProduct96(uint32_t q, uint64_t nlo) {
    const uint64_t p0 = uint64_t(q)*uint32_t(nlo);
    const uint64_t p1 = uint64_t(q)*uint32_t(nlo>>32)+(p0>>32);
    const uint64_t p2 = uint64_t(q)*10u+(p1>>32);
    if (p2 < (1ULL<<32)) return -1;
    if (p2 > (1ULL<<32)) return 1;
    return (uint32_t(p0)|uint32_t(p1)) ? 1 : 0;
}

// COLD perjob. Caller supplies the full actual query/halo envelope, NOT only
// owned output positions. Both endpoint highs must be10 and cannot wrap.
C21_HD JobMu buildJob(uint32_t highMin, uint64_t minLow,
                       uint32_t highMax, uint64_t maxLow) {
    JobMu out{minLow,maxLow,0,0};
    if (highMin!=10 || highMax!=10 || maxLow<minLow ||
        maxLow-minLow >= 100ULL*(1ULL<<32)) return out;
    uint32_t mu=0;
    // N>10R implies quotient<2^29. Cold29-bit exact search, not perpoint.
    for (int bit=28;bit>=0;--bit) {
        const uint32_t candidate=mu|(1u<<bit);
        if (compareProduct96(candidate,maxLow)<=0) mu=candidate;
    }
    if (compareProduct96(mu,maxLow)>0 || compareProduct96(mu+1,maxLow)<=0)
        return out;
    out.muLower=mu;out.ready=Ready;
    return out;
}

C21_HD bool admits(const JobMu& job, uint64_t low) {
    return job.ready==Ready && low>=job.minLow && low<=job.maxLow;
}

// Canonical ADD/MAD columns for the HOST oracle only. Device uses C20 PTX.
// No host code here constitutes CUDA compiler/device validation.
#if !defined(__CUDA_ARCH__)
C21_HD void hostAddProduct(uint32_t& l,uint32_t& m,uint32_t& h,
                           uint32_t x,uint32_t y) {
    const uint64_t product=uint64_t(x)*y;
    uint64_t s=uint64_t(l)+uint32_t(product);l=uint32_t(s);
    s=uint64_t(m)+(product>>32)+(s>>32);m=uint32_t(s);
    h+=uint32_t(s>>32);
}
C21_HD Value hostSquare(Value a,uint32_t n0,uint32_t n1,uint32_t np,uint32_t mu) {
    const uint64_t xx=uint64_t(a.x)*a.x;
    uint32_t l=uint32_t(xx),m=uint32_t(xx>>32),h=0;
    const uint32_t q0=l*np;hostAddProduct(l,m,h,q0,n0);
    l=m;m=h;h=0;
    hostAddProduct(l,m,h,q0,n1);
    hostAddProduct(l,m,h,a.x,a.y);hostAddProduct(l,m,h,a.x,a.y);
    const uint32_t q1=l*np;hostAddProduct(l,m,h,q1,n0);
    l=m;m=h;h=0;
    hostAddProduct(l,m,h,q0,10);
    hostAddProduct(l,m,h,a.x,2*a.z);
    hostAddProduct(l,m,h,q1,n1);hostAddProduct(l,m,h,a.y,a.y);
    const uint32_t t0=l;l=m;m=h;h=0;
    hostAddProduct(l,m,h,q1,10);hostAddProduct(l,m,h,a.y,2*a.z);
    const uint32_t t1=l,t2=a.z*a.z+m,q=uint32_t(uint64_t(t2)*mu>>32);
    const uint64_t p0=uint64_t(q)*n0,p1=uint64_t(q)*n1+(p0>>32);
    uint64_t s=uint64_t(t0)-uint32_t(p0);Value d{uint32_t(s),0,0};
    s=uint64_t(t1)-uint32_t(p1)-uint32_t(s>>63);d.y=uint32_t(s);
    d.z=t2-(10*q+uint32_t(p1>>32))-uint32_t(s>>63);
    return d;
}
#endif

C21_HD Value squareAfterW3(Value a,uint32_t n0,uint32_t n1,uint32_t np,uint32_t mu) {
#if defined(__CUDA_ARCH__)
    return myr_r64lazy32::square(a,n0,n1,np,mu);
#else
    return hostSquare(a,n0,n1,np,mu);
#endif
}

C21_HD Value shiftOnly(Value a,uint32_t bits) {
    if (!bits) return a;
#if defined(__CUDA_ARCH__)
    Value t;
    asm("{\n\t.reg .u32 t0,t1,t2;\n\t"
        "shl.b32 t0,%3,%6;\n\tshf.l.wrap.b32 t1,%3,%4,%6;\n\t"
        "shf.l.wrap.b32 t2,%4,%5,%6;\n\t"
        "mov.u32 %0,t0;\n\tmov.u32 %1,t1;\n\tmov.u32 %2,t2;\n\t}"
        : "=r"(t.x),"=r"(t.y),"=r"(t.z)
        : "r"(a.x),"r"(a.y),"r"(a.z),"r"(bits));
    return t;
#else
    return {a.x<<bits,(a.y<<bits)|(a.x>>(32-bits)),
            (a.z<<bits)|(a.y>>(32-bits))};
#endif
}

// For seed bits<=26 or finalbit<=1, input<2N. One quotient, no canon.
C21_HD Value shiftReduce(Value a,uint32_t bits,uint32_t n0,uint32_t n1,uint32_t mu) {
    if (!bits) return a;
    Value t=shiftOnly(a,bits);
#if defined(__CUDA_ARCH__)
    Value d;
    asm("{\n\t.reg .u32 q,p0,p1,p2,r0,r1,r2;\n\t"
        "mul.hi.u32 q,%5,%8;\n\t"
        "mul.lo.u32 p0,q,%6;\n\tmul.hi.u32 p1,q,%6;\n\t"
        "mad.lo.cc.u32 p1,q,%7,p1;\n\tmadc.hi.u32 p2,q,%7,0;\n\t"
        "mad.lo.u32 p2,q,10,p2;\n\t"
        "sub.cc.u32 r0,%3,p0;\n\tsubc.cc.u32 r1,%4,p1;\n\tsubc.u32 r2,%5,p2;\n\t"
        "mov.u32 %0,r0;\n\tmov.u32 %1,r1;\n\tmov.u32 %2,r2;\n\t}"
        : "=r"(d.x),"=r"(d.y),"=r"(d.z)
        : "r"(t.x),"r"(t.y),"r"(t.z),"r"(n0),"r"(n1),"r"(mu));
    return d;
#else
    const uint32_t q=uint32_t(uint64_t(t.z)*mu>>32);
    const uint64_t p0=uint64_t(q)*n0,p1=uint64_t(q)*n1+(p0>>32);
    uint64_t s=uint64_t(t.x)-uint32_t(p0);Value d{uint32_t(s),0,0};
    s=uint64_t(t.y)-uint32_t(p1)-uint32_t(s>>63);d.y=uint32_t(s);
    d.z=t.z-(10*q+uint32_t(p1>>32))-uint32_t(s>>63);
    return d;
#endif
}

C21_HD bool equals(Value a,Value b) { return a.x==b.x && a.y==b.y && a.z==b.z; }

// HD annotation is required for a real NVCC host/device consumer. The sealed
// C20 helper is device-only under CUDACC; do not call it from the host variant.
C21_HD uint32_t negativeInverse32(uint32_t n0) {
    uint32_t x=n0;
    x*=2u-n0*x;x*=2u-n0*x;x*=2u-n0*x;x*=2u-n0*x;
    return 0u-x;
}

// PRECONDITION: job was built cold, immutable, and admits(low).
// Output equals original parent's Euler(2) oracle, NOT exact primality.
C21_HD bool testAdmitted(uint64_t low,const JobMu& job) {
    if (!(low&1)) return false;
    const uint32_t n0=uint32_t(low),n1=uint32_t(low>>32),mu=job.muLower;
    const uint32_t np=negativeInverse32(n0);
    Value a{0,0,1}; // R64 encoded1; R<N, no hidden warm assumption
    C21_UNROLL for (int j=0;j<6;++j) a=shiftReduce(a,26,n0,n1,mu);
    a=shiftReduce(a,4u+uint32_t(low>>60),n0,n1,mu); // prefix160..175
    const uint64_t e=(low-1)>>1;
    a=squareAfterW3(a,n0,n1,np,mu);
    a=shiftOnly(a,uint32_t((e>>58)&1)); // input of next square<4N
    for (int bit=57;bit>=3;bit-=3) {
        a=squareAfterW3(a,n0,n1,np,mu);
        a=squareAfterW3(a,n0,n1,np,mu);
        a=squareAfterW3(a,n0,n1,np,mu);
        a=shiftOnly(a,uint32_t((e>>(bit-2))&7)); // input<256N
    }
    a=squareAfterW3(a,n0,n1,np,mu); //59 squares total
    a=shiftReduce(a,uint32_t(e&1),n0,n1,mu); // final state<2N
    // Jacobi(2,N) depends only on low%8. Two representatives in[0,2N).
    if (((low>>1)^(low>>2))&1)
        return equals(a,Value{n0,n1,9}) || equals(a,Value{n0<<1,
            uint32_t((low<<1)>>32),19u+uint32_t(low>>63)});
    return equals(a,Value{0,0,1}) || equals(a,Value{n0,n1,11});
}

// SAFE entry when the full-query range cannot be guaranteed at callsite.
// No32B stateful cache is REQUIRED on the admitted hot path. The COLD fallback
// is the unchanged exact H10 parent, with no alleged gain for invalid jobs.
// Root may select the two paths once uniformly perjob to avoid code inflation.
C21_HD bool testWithFallback(uint64_t low,const JobMu& job,bool* fellBack=nullptr) {
    if (!admits(job,low)) {
        if (fellBack) *fellBack=true;
        return pgn_barrett70::test(low);
    }
    if (fellBack) *fellBack=false;
    return testAdmitted(low,job);
}

#undef C21_HD
#undef C21_UNROLL
} // namespace myr_r64lazy32_prp


// C25 independent SOURCE. NOT compiled/tested/GPU/Native qualified.
// Keep sealed C20/C21,36C5,C24/C24s and M553 unchanged.
// Numerical domain/bucket/inverse/fallback are EXACTLY the existing C21 ones.
namespace myr_r64_pairfold {
using Value=myr_r64lazy32::Value;
using JobMu=myr_r64lazy32_prp::JobMu;
struct Folded {Value v;}; // construction invariant0<=v<2N
struct Wide {Value v;};   // construction invariant0<=v<256N
static_assert(sizeof(Folded)==12 && sizeof(Wide)==12,"No payload expansion");
#if defined(__CUDACC__)
#define C25_HD __host__ __device__ __forceinline__
#define C25_UNROLL _Pragma("unroll")
#else
#define C25_HD inline
#define C25_UNROLL
#endif

// ONLY a Folded input is admitted. Raw output<45N, included in Wide.
// This is the SAME C20 column arithmetic through the exact raw t words,
// with NO final quotient/p*N/subtract. All third-word carries are retained.
C25_HD Wide rawSquare(Folded input,uint32_t n0,uint32_t n1,uint32_t np32) {
    const Value a=input.v;Value t;
#if defined(__CUDA_ARCH__)
    asm volatile(
        "{\n\t"
        ".reg .u32 l,m,h,q0,q1,z2,t0,t1,t2;\n\t"
        "add.u32 z2,%5,%5;\n\t"
        "mul.lo.u32 l,%3,%3;\n\t"
        "mul.hi.u32 m,%3,%3;\n\t"
        "mul.lo.u32 q0,l,%8;\n\t"
        "mad.lo.cc.u32 l,q0,%6,l;\n\t"
        "madc.hi.cc.u32 m,q0,%6,m;\n\t"
        "addc.u32 h,0,0;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q0,%7,l;\n\t"
        "madc.hi.u32 m,q0,%7,m;\n\t"
        "mov.u32 h,0;\n\t"
        "mad.lo.cc.u32 l,%3,%4,l;\n\t"
        "madc.hi.cc.u32 m,%3,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mad.lo.cc.u32 l,%3,%4,l;\n\t"
        "madc.hi.cc.u32 m,%3,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mul.lo.u32 q1,l,%8;\n\t"
        "mad.lo.cc.u32 l,q1,%6,l;\n\t"
        "madc.hi.cc.u32 m,q1,%6,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q0,10,l;\n\t"
        "madc.hi.u32 m,q0,10,m;\n\t"
        "mad.lo.cc.u32 l,%3,z2,l;\n\t"
        "madc.hi.u32 m,%3,z2,m;\n\t"
        "mov.u32 h,0;\n\t"
        "mad.lo.cc.u32 l,q1,%7,l;\n\t"
        "madc.hi.cc.u32 m,q1,%7,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mad.lo.cc.u32 l,%4,%4,l;\n\t"
        "madc.hi.cc.u32 m,%4,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mov.u32 t0,l;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q1,10,l;\n\t"
        "madc.hi.u32 m,q1,10,m;\n\t"
        "mad.lo.cc.u32 l,%4,z2,l;\n\t"
        "madc.hi.u32 m,%4,z2,m;\n\t"
        "mov.u32 t1,l;\n\t"
        "mad.lo.u32 t2,%5,%5,m;\n\t"
        "mov.u32 %0,t0;\n\t"
        "mov.u32 %1,t1;\n\t"
        "mov.u32 %2,t2;\n\t"
        "}\n"
        : "=r"(t.x),"=r"(t.y),"=r"(t.z)
        : "r"(a.x),"r"(a.y),"r"(a.z),"r"(n0),"r"(n1),"r"(np32));
#else
    // Portable host arithmetic counterpart, NOT separately compiled here.
    using myr_r64lazy32_prp::hostAddProduct;
    const uint64_t xx=uint64_t(a.x)*a.x;
    uint32_t l=uint32_t(xx),m=uint32_t(xx>>32),h=0;
    const uint32_t q0=l*np32;hostAddProduct(l,m,h,q0,n0);
    l=m;m=h;h=0;
    hostAddProduct(l,m,h,q0,n1);
    hostAddProduct(l,m,h,a.x,a.y);hostAddProduct(l,m,h,a.x,a.y);
    const uint32_t q1=l*np32;hostAddProduct(l,m,h,q1,n0);
    l=m;m=h;h=0;
    hostAddProduct(l,m,h,q0,10);hostAddProduct(l,m,h,a.x,2*a.z);
    hostAddProduct(l,m,h,q1,n1);hostAddProduct(l,m,h,a.y,a.y);
    t.x=l;l=m;m=h;h=0;
    hostAddProduct(l,m,h,q1,10);hostAddProduct(l,m,h,a.y,2*a.z);
    t.y=l;t.z=a.z*a.z+m;
#endif
    return {t};
}

// Full square of ANY constructed Wide value: sealed C20/C21 implementation.
C25_HD Folded squareAndFold(Wide a,uint32_t n0,uint32_t n1,uint32_t np,uint32_t mu) {
    return {myr_r64lazy32_prp::squareAfterW3(a.v,n0,n1,np,mu)};
}

// Caller must use the SAME C21 cold JobMu builder/admission. No new metadata.
// This changes temporary residue representatives, NOT the final Euler oracle.
C25_HD bool testAdmitted(uint64_t low,const JobMu& job) {
    if (!(low&1)) return false;
    const uint32_t n0=uint32_t(low),n1=uint32_t(low>>32),mu=job.muLower;
    const uint32_t np=myr_r64lazy32_prp::negativeInverse32(n0);
    Value seed{0,0,1};
    C25_UNROLL for(int j=0;j<6;++j)
        seed=myr_r64lazy32_prp::shiftReduce(seed,26,n0,n1,mu);
    seed=myr_r64lazy32_prp::shiftReduce(seed,4u+uint32_t(low>>60),n0,n1,mu);
    const uint64_t e=(low-1)>>1;
    Wide a=rawSquare(Folded{seed},n0,n1,np); //raw1, input<2N, output<45N
    a.v=myr_r64lazy32_prp::shiftOnly(a.v,uint32_t((e>>58)&1)); //now<90N
    for(int bit=57;bit>=3;bit-=3) {
        Folded b=squareAndFold(a,n0,n1,np,mu); //input<90N or256N; output<2N
        Wide c=rawSquare(b,n0,n1,np); //raw19, input<2N; output<45N
        b=squareAndFold(c,n0,n1,np,mu); //input<45N; output<2N
        a.v=myr_r64lazy32_prp::shiftOnly(b.v,uint32_t((e>>(bit-2))&7)); //now<256N
    }
    Folded b=squareAndFold(a,n0,n1,np,mu); //folded39, same final square
    const Value last=myr_r64lazy32_prp::shiftReduce(b.v,uint32_t(e&1),n0,n1,mu);
    if(((low>>1)^(low>>2))&1)
        return myr_r64lazy32_prp::equals(last,Value{n0,n1,9}) ||
          myr_r64lazy32_prp::equals(last,Value{n0<<1,uint32_t((low<<1)>>32),19u+uint32_t(low>>63)});
    return myr_r64lazy32_prp::equals(last,Value{0,0,1}) ||
           myr_r64lazy32_prp::equals(last,Value{n0,n1,11});
}

C25_HD bool testWithFallback(uint64_t low,const JobMu& job,bool* fellBack=nullptr) {
    if(!myr_r64lazy32_prp::admits(job,low)) {
        if(fellBack)*fellBack=true;
        return pgn_barrett70::test(low);
    }
    if(fellBack)*fellBack=false;
    return myr_r64_pairfold::testAdmitted(low,job);
}
#undef C25_HD
#undef C25_UNROLL
} // namespace myr_r64_pairfold


#if defined(__CUDACC__)
#define C29_HD __host__ __device__ __forceinline__
#define C29_SEED_UNROLL _Pragma("unroll")
#else
#define C29_HD inline
#define C29_SEED_UNROLL
#endif

namespace myr_r64_pairfold_stream {
using Value=myr_r64_pairfold::Value;
using JobMu=myr_r64_pairfold::JobMu;
using Folded=myr_r64_pairfold::Folded;
using Wide=myr_r64_pairfold::Wide;

// SAME admission as C25: odd low, real H10 JobMu, exact prepaid muLower.
// The arithmetic producer/RAW/FOLD bodies are the sealed C25/C21 ones.
C29_HD bool testAdmitted(uint64_t low,const JobMu& job) {
    if(!(low&1))return false;
    const uint32_t n0=uint32_t(low),n1=uint32_t(low>>32),mu=job.muLower;
    const uint32_t np=myr_r64lazy32_prp::negativeInverse32(n0);
    Value seed{0,0,1};
    C29_SEED_UNROLL for(int j=0;j<6;++j)
        seed=myr_r64lazy32_prp::shiftReduce(seed,26,n0,n1,mu);
    seed=myr_r64lazy32_prp::shiftReduce(seed,4u+uint32_t(low>>60),n0,n1,mu);

    Wide a=myr_r64_pairfold::rawSquare(Folded{seed},n0,n1,np);
    a.v=myr_r64lazy32_prp::shiftOnly(a.v,uint32_t((low>>59)&1u));

    // D=(low>>2)&(2^57-1). The marker is one bit BELOW the surviving D bits.
    // After exactly 19 shifts by3, D is gone and the marker alone reaches bit63.
    // No shift by64, signed shift, variable trip quota or early-oracle decision.
    uint64_t windows=((low&~uint64_t(3))<<5)|uint64_t(64);
    #if defined(__CUDA_ARCH__)
    #pragma unroll 1
    #endif
    do {
        Folded b=myr_r64_pairfold::squareAndFold(a,n0,n1,np,mu);
        const Wide c=myr_r64_pairfold::rawSquare(b,n0,n1,np);
        b=myr_r64_pairfold::squareAndFold(c,n0,n1,np,mu);
        a.v=myr_r64lazy32_prp::shiftOnly(b.v,uint32_t(windows>>61));
        windows<<=3;
    } while(windows!=(uint64_t(1)<<63));

    const Folded b=myr_r64_pairfold::squareAndFold(a,n0,n1,np,mu);
    const Value last=myr_r64lazy32_prp::shiftReduce(b.v,uint32_t((low>>1)&1u),n0,n1,mu);
    if(((low>>1)^(low>>2))&1u)
        return myr_r64lazy32_prp::equals(last,Value{n0,n1,9}) ||
          myr_r64lazy32_prp::equals(last,Value{n0<<1,uint32_t((low<<1)>>32),19u+uint32_t(low>>63)});
    return myr_r64lazy32_prp::equals(last,Value{0,0,1}) ||
           myr_r64lazy32_prp::equals(last,Value{n0,n1,11});
}

C29_HD bool testWithFallback(uint64_t low,const JobMu& job,bool* fellBack=nullptr) {
    if(!myr_r64lazy32_prp::admits(job,low)) {
        if(fellBack)*fellBack=true;
        return pgn_barrett70::test(low);
    }
    if(fellBack)*fellBack=false;
    return myr_r64_pairfold_stream::testAdmitted(low,job);
}
} // namespace myr_r64_pairfold_stream

#undef C29_HD
#undef C29_SEED_UNROLL

#if defined(__CUDACC__)
#define M600_HD __host__ __device__ __forceinline__
#define M600_SEED_UNROLL _Pragma("unroll")
#else
#define M600_HD inline
#define M600_SEED_UNROLL
#endif
namespace m600_fourbit_orbit96 {
using Value=myr_r64lazy32::Value;
using JobMu=myr_r64lazy32_prp::JobMu;
// Internal contract: 0<=a<45N, N=10*2^64+low. Exact same raw columns as C25.
// No call is made through C25's narrower Folded<2N interface.
M600_HD Value rawSquare45(Value a,uint32_t n0,uint32_t n1,uint32_t np32) {
    Value t;
#if defined(__CUDA_ARCH__)
    asm volatile(
        "{\n\t"
        ".reg .u32 l,m,h,q0,q1,z2,t0,t1,t2;\n\t"
        "add.u32 z2,%5,%5;\n\t"
        "mul.lo.u32 l,%3,%3;\n\t"
        "mul.hi.u32 m,%3,%3;\n\t"
        "mul.lo.u32 q0,l,%8;\n\t"
        "mad.lo.cc.u32 l,q0,%6,l;\n\t"
        "madc.hi.cc.u32 m,q0,%6,m;\n\t"
        "addc.u32 h,0,0;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q0,%7,l;\n\t"
        "madc.hi.u32 m,q0,%7,m;\n\t"
        "mov.u32 h,0;\n\t"
        "mad.lo.cc.u32 l,%3,%4,l;\n\t"
        "madc.hi.cc.u32 m,%3,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mad.lo.cc.u32 l,%3,%4,l;\n\t"
        "madc.hi.cc.u32 m,%3,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mul.lo.u32 q1,l,%8;\n\t"
        "mad.lo.cc.u32 l,q1,%6,l;\n\t"
        "madc.hi.cc.u32 m,q1,%6,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q0,10,l;\n\t"
        "madc.hi.u32 m,q0,10,m;\n\t"
        "mad.lo.cc.u32 l,%3,z2,l;\n\t"
        "madc.hi.u32 m,%3,z2,m;\n\t"
        "mov.u32 h,0;\n\t"
        "mad.lo.cc.u32 l,q1,%7,l;\n\t"
        "madc.hi.cc.u32 m,q1,%7,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mad.lo.cc.u32 l,%4,%4,l;\n\t"
        "madc.hi.cc.u32 m,%4,%4,m;\n\t"
        "addc.u32 h,h,0;\n\t"
        "mov.u32 t0,l;\n\t"
        "mov.u32 l,m;\n\t"
        "mov.u32 m,h;\n\t"
        "mad.lo.cc.u32 l,q1,10,l;\n\t"
        "madc.hi.u32 m,q1,10,m;\n\t"
        "mad.lo.cc.u32 l,%4,z2,l;\n\t"
        "madc.hi.u32 m,%4,z2,m;\n\t"
        "mov.u32 t1,l;\n\t"
        "mad.lo.u32 t2,%5,%5,m;\n\t"
        "mov.u32 %0,t0;\n\t"
        "mov.u32 %1,t1;\n\t"
        "mov.u32 %2,t2;\n\t"
        "}\n"
        : "=r"(t.x),"=r"(t.y),"=r"(t.z)
        : "r"(a.x),"r"(a.y),"r"(a.z),"r"(n0),"r"(n1),"r"(np32));
#else
    // Portable host arithmetic counterpart, NOT separately compiled here.
    using myr_r64lazy32_prp::hostAddProduct;
    const uint64_t xx=uint64_t(a.x)*a.x;
    uint32_t l=uint32_t(xx),m=uint32_t(xx>>32),h=0;
    const uint32_t q0=l*np32;hostAddProduct(l,m,h,q0,n0);
    l=m;m=h;h=0;
    hostAddProduct(l,m,h,q0,n1);
    hostAddProduct(l,m,h,a.x,a.y);hostAddProduct(l,m,h,a.x,a.y);
    const uint32_t q1=l*np32;hostAddProduct(l,m,h,q1,n0);
    l=m;m=h;h=0;
    hostAddProduct(l,m,h,q0,10);hostAddProduct(l,m,h,a.x,2*a.z);
    hostAddProduct(l,m,h,q1,n1);hostAddProduct(l,m,h,a.y,a.y);
    t.x=l;l=m;m=h;h=0;
    hostAddProduct(l,m,h,q1,10);hostAddProduct(l,m,h,a.y,2*a.z);
    t.y=l;t.z=a.z*a.z+m;
#endif
    return t;
}

// Generic true: a<22276N,bits<=15. False: a<45N,bits<=7 (tail), OR
// the proved reached hot a<(10036371/4096)N,bits<=15,delta<29/25.
// The latter always has X<2^94; generic large inputs STILL need true.
// Digit0 MUST still execute the linear fold; never early-return a here.
// The high part after shifting may need33bits. Its extra bit participates in
// q BEFORE the low96 subtraction. The actual residue is proved nonnegative
// and<4N (or<2N in the final small case), so modulo2^96 subtraction is exact.
template<bool Carry97>
M600_HD Value shiftFold(Value a,uint32_t bits,uint32_t n0,uint32_t n1,uint32_t mu) {
    Value t;uint32_t carry=0;
#if defined(__CUDA_ARCH__)
    // PTX SHF has defined zero-distance semantics. No bits==0 branch is
    // required: the concatenation [0,a.z]<<0 has a zero high word.
    if constexpr(Carry97) {
        asm("{\n\t.reg .u32 x,y,z,h;\n\t"
            "shl.b32 x,%4,%7;\n\tshf.l.wrap.b32 y,%4,%5,%7;\n\t"
            "shf.l.wrap.b32 z,%5,%6,%7;\n\tshf.l.wrap.b32 h,%6,0,%7;\n\t"
            "mov.u32 %0,x;\n\tmov.u32 %1,y;\n\tmov.u32 %2,z;\n\tmov.u32 %3,h;\n\t}"
            : "=r"(t.x),"=r"(t.y),"=r"(t.z),"=r"(carry)
            : "r"(a.x),"r"(a.y),"r"(a.z),"r"(bits));
    } else {
        asm("{\n\t.reg .u32 x,y,z;\n\t"
            "shl.b32 x,%3,%6;\n\tshf.l.wrap.b32 y,%3,%4,%6;\n\t"
            "shf.l.wrap.b32 z,%4,%5,%6;\n\t"
            "mov.u32 %0,x;\n\tmov.u32 %1,y;\n\tmov.u32 %2,z;\n\t}"
            : "=r"(t.x),"=r"(t.y),"=r"(t.z)
            : "r"(a.x),"r"(a.y),"r"(a.z),"r"(bits));
    }
    Value d;
    asm("{\n\t.reg .u32 q,p0,p1,p2,r0,r1,r2;\n\t"
        "mul.hi.u32 q,%5,%8;\n\t"
        "mad.lo.u32 q,%9,%8,q;\n\t"
        "mul.lo.u32 p0,q,%6;\n\tmul.hi.u32 p1,q,%6;\n\t"
        "mad.lo.cc.u32 p1,q,%7,p1;\n\tmadc.hi.u32 p2,q,%7,0;\n\t"
        "mad.lo.u32 p2,q,10,p2;\n\t"
        "sub.cc.u32 r0,%3,p0;\n\tsubc.cc.u32 r1,%4,p1;\n\tsubc.u32 r2,%5,p2;\n\t"
        "mov.u32 %0,r0;\n\tmov.u32 %1,r1;\n\tmov.u32 %2,r2;\n\t}"
        : "=r"(d.x),"=r"(d.y),"=r"(d.z)
        : "r"(t.x),"r"(t.y),"r"(t.z),"r"(n0),"r"(n1),"r"(mu),"r"(carry));
    return d;
#else
    // The portable words use64-bit temporaries, so bits==0 never causes a
    // C++ shift by32; the high temporary carries the extra97th bit exactly.
    const uint64_t x=uint64_t(a.x)<<bits;
    const uint64_t y=(uint64_t(a.y)<<bits)|(x>>32);
    const uint64_t highShift=(uint64_t(a.z)<<bits)|(y>>32);
    t={uint32_t(x),uint32_t(y),uint32_t(highShift)};
    if constexpr(Carry97)carry=uint32_t(highShift>>32);
    const uint32_t q=uint32_t((uint64_t(t.z)*mu)>>32)+carry*mu;
    const uint64_t p0=uint64_t(q)*n0;
    const uint64_t p1=uint64_t(q)*n1+(p0>>32);
    const uint32_t p2=uint32_t(uint64_t(q)*10+(p1>>32));
    uint64_t z=uint64_t(t.x)-uint32_t(p0);Value d{uint32_t(z),0,0};
    z=uint64_t(t.y)-uint32_t(p1)-uint32_t(z>>63);d.y=uint32_t(z);
    d.z=t.z-p2-uint32_t(z>>63);return d;
#endif
}

M600_HD bool admits(const JobMu& job,uint64_t low) {
    return myr_r64lazy32_prp::admits(job,low) && job.maxLow>=job.minLow &&
           job.maxLow-job.minLow<=(uint64_t(1)<<36);
}

// PRECONDITION: same exact C21 ready JobMu, actual H10, plus the narrow span.
// This is not an unchecked arbitrary-high or arbitrary-mu entry point.
M600_HD bool testAdmitted(uint64_t low,const JobMu& job) {
    if(!(low&1))return false;
    const uint32_t n0=uint32_t(low),n1=uint32_t(low>>32),mu=job.muLower;
    const uint32_t np=myr_r64lazy32_prp::negativeInverse32(n0);
    Value a{0,0,1};
    M600_SEED_UNROLL for(int j=0;j<6;++j)
        a=myr_r64lazy32_prp::shiftReduce(a,26,n0,n1,mu);
    a=myr_r64lazy32_prp::shiftReduce(a,4u+uint32_t(low>>60),n0,n1,mu);

    // Same fourteen digits as the proved sentinel loop. The marker remains
    // below every consumed digit. A constant trip count permits full unroll;
    // no arithmetic, input domain, digit or tail operation changes.
    uint64_t stream=((low&~uint64_t(15))<<4)|uint64_t(128);
    #if defined(__CUDA_ARCH__)
    #pragma unroll
    #endif
    for(unsigned group_index=0;group_index<14u;++group_index) {
        a=rawSquare45(a,n0,n1,np); // input<4N, output<177N<256N
        a=myr_r64lazy32_prp::squareAfterW3(a,n0,n1,np,mu); // <2N
        a=rawSquare45(a,n0,n1,np); // <45N
        a=rawSquare45(a,n0,n1,np); // <22276N
        a=shiftFold<false>(a,uint32_t(stream>>60),n0,n1,mu); // <11N/8; reached carry97==0
        stream<<=4;
    }

    // Last three exponent bits are low3..1. Their digit<=7 permits a plain
    // 96-bit shift/fold and restores<2N for the UNCHANGED Euler oracle.
    a=rawSquare45(a,n0,n1,np); // <177N
    a=myr_r64lazy32_prp::squareAfterW3(a,n0,n1,np,mu); // <2N
    a=rawSquare45(a,n0,n1,np); // <45N
    a=shiftFold<false>(a,uint32_t((low>>1)&7u),n0,n1,mu); // <2N
    if(((low>>1)^(low>>2))&1u)
        return myr_r64lazy32_prp::equals(a,Value{n0,n1,9}) ||
          myr_r64lazy32_prp::equals(a,Value{n0<<1,uint32_t((low<<1)>>32),19u+uint32_t(low>>63)});
    return myr_r64lazy32_prp::equals(a,Value{0,0,1}) ||
           myr_r64lazy32_prp::equals(a,Value{n0,n1,11});
}

// A wide/unready envelope uses the retained C29 path, not a truncated span.
// fellBack means this private candidate was not used; C29 keeps its own guard.
M600_HD bool testWithFallback(uint64_t low,const JobMu& job,bool* fellBack=nullptr) {
    if(!m600_fourbit_orbit96::admits(job,low)) {
        if(fellBack)*fellBack=true;
        return myr_r64_pairfold_stream::testWithFallback(low,job);
    }
    if(fellBack)*fellBack=false;
    return m600_fourbit_orbit96::testAdmitted(low,job);
}
} // namespace m600_fourbit_orbit96
#undef M600_HD
#undef M600_SEED_UNROLL

#if defined(__CUDACC__)
#define M586_HD __host__ __device__ __forceinline__
#else
#define M586_HD inline
#endif
namespace pgn_stateful_u160 {
struct State {uint32_t bucketTag=0,muLower=0;};
static_assert(sizeof(State)==8,"Same two-word per-owner state");
constexpr uint64_t BucketMask=(uint64_t(1)<<36)-1;
M586_HD bool test(uint64_t low,State& state){
    if(!(low&1))return false;
    const uint32_t tag=uint32_t(low>>36);
    const uint64_t first=uint64_t(tag)<<36,last=first|BucketMask;
    if(!state.muLower||state.bucketTag!=tag){
        const auto built=myr_r64lazy32_prp::buildJob(10,first,10,last);
        if(built.ready!=myr_r64lazy32_prp::Ready)
            return pgn_barrett70::test(low);
        state.bucketTag=tag;state.muLower=built.muLower;
    }
    // The exact C21 builder was run for THIS complete2^36 bucket. Reversed,
    // halo and repair queries are admitted by tag, never clipped/dropped.
    // Keep real bounds in JobMu to make M583's <=2^36 proof contract explicit.
    // testAdmitted reads only muLower; compiler/register consequences unpaid.
    const myr_r64lazy32_prp::JobMu hot{first,last,state.muLower,myr_r64lazy32_prp::Ready};
    return m600_fourbit_orbit96::testAdmitted(low,hot);
}
} // namespace pgn_stateful_u160
#undef M586_HD


typedef unsigned char uint8_t;
typedef unsigned __int128 uint128_t;
#define HIGH_64 10ULL
#define PARANOID 0
// ===== Thanks to Perig for this code ===== 
//       vvvvvvvvvvvvvvvvvvvvvvvvvvvvv

// (a::b) <<= c
__host__ __device__ static inline __attribute__((always_inline))
void my_shld64(uint64_t * a, uint64_t * b, uint64_t c)
{
#if PARANOID
	assert(c < 64);
#endif
	if (c == 0) {
	} else {
		(*a) = ((*a) << c) | ((*b) >> (64 - c));
		(*b) <<= c;
	}
}

// borrow::diff = a - b - borrow_in
static inline __attribute__((always_inline))
__host__ __device__ uint8_t my_sbb64(uint8_t borrow_in, uint64_t a, uint64_t b, uint64_t * diff)
{
    uint64_t tmp1 = a - borrow_in;
    uint8_t borrow = (tmp1 > a);

    uint64_t tmp2 = tmp1 - b;
    borrow |= (tmp2 > tmp1);
    *diff = tmp2;
    return borrow;
}

// count leading zeroes in binary representation
static inline __attribute__((always_inline))
__host__ __device__ uint64_t my_clz64(uint64_t n)
{
#ifdef __CUDA_ARCH__
    return __clzll(n);
#else
	if (n == 0)
		return 64;
	uint64_t r = 0;
	if ((n & (0xFFFFFFFFull << 32)) == 0)
		r += 32, n <<= 32;
	if ((n & (0xFFFFull << 48)) == 0)
		r += 16, n <<= 16;
	if ((n & (0xFFull << 56)) == 0)
		r += 8, n <<= 8;
	if ((n & (0xFull << 60)) == 0)
		r += 4, n <<= 4;
	if ((n & (0x3ull << 62)) == 0)
		r += 2, n <<= 2;
	if ((n & (0x1ull << 63)) == 0)
		r += 1;
	return r;
#endif
}

static inline __attribute__((always_inline))
__host__ __device__ uint64_t montgomeryInverse64(uint64_t mod_lo)
{
	uint64_t x = (3ull * mod_lo) ^ 2ull;	// 5 bits acurate
	uint64_t t = 1ull - mod_lo * x;
	x *= 1 + t;		// 10 bits accurate
	t *= t;
	x *= 1 + t;		// 20 bits accurate
	t *= t;
	x *= 1 + t;		// 40 bits accurate
	t *= t;
	x *= 1 + t;		// 80 bits accurate , i.e. > 64 bits
	return 0 - x;
}

// subtract the modulus 'mod' multiple times from the input number 'res', if needed
static inline __attribute__((always_inline))
__host__ __device__ void ciosSubtract128(uint64_t * res_lo, uint64_t * res_hi, uint64_t mod_lo, uint64_t mod_hi)
{
	uint64_t n_lo, n_hi;
	uint64_t t_lo, t_hi;
	uint8_t b;
	n_lo = *res_lo;
	n_hi = *res_hi;
	// save, subtract the modulus until a borrows occurs
	do {
		t_lo = n_lo;
		t_hi = n_hi;
		b = my_sbb64(0, n_lo, mod_lo, &n_lo);
		b = my_sbb64(b, n_hi, mod_hi, &n_hi);
	}
	while (b == 0);
	// get the saved values
	*res_lo = t_lo;
	*res_hi = t_hi;
}

static inline __attribute__((always_inline))
__host__ __device__ void ciosConstants128(uint64_t mod_lo, uint64_t mod_hi, uint64_t * magic_lo, uint64_t * magic_hi)
{
	// computes 2^128 % mod
	uint128_t m = ((uint128_t) mod_hi << 64) + mod_lo;
	uint128_t t = -m;	// 2^128-m
	t %= m;			// (2^128-m) % m
	*magic_lo = (uint64_t) t;
	*magic_hi = (uint64_t) (t >> 64);
#if PARANOID
	assert(*magic_hi <= mod_hi);
#endif
}

static inline __attribute__((always_inline))
__host__ __device__ void ciosModSquare128(uint64_t * res_lo, uint64_t * res_hi, uint64_t mod_lo, uint64_t mod_hi, uint64_t mmagic)
{
	uint64_t n_lo = *res_lo, n_hi = *res_hi;
	uint128_t cs, cc;
	uint64_t t0, t1, t2, m;

	cc = (uint128_t) n_lo *n_lo;	// #1
	t0 = (uint64_t) cc;
	cc = cc >> 64;
	cc += (uint128_t) n_lo *(n_hi + n_hi);	// #2
	t1 = (uint64_t) cc;
	cc = cc >> 64;
	t2 = (uint64_t) cc;
#if PARANOID
	assert(cc >> 64 == 0);
#endif

	m = t0 * mmagic;	// #3
	cs = (uint128_t) m *mod_lo;	// #4
	cs += t0;
	cs = cs >> 64;

    cs += (uint128_t) m *mod_hi; // CAN OPTIMIZE
	cs += t1;
    
	t0 = (uint64_t) cs;
	cs = cs >> 64;
	cs += t2;
	t1 = (uint64_t) cs;
	cs = cs >> 64;
	t2 = (uint64_t) cs;
#if PARANOID
	assert(cs >> 64 == 0);
#endif

	cc = (uint128_t) n_hi *n_hi;	// #6
	cc += t1;
	t1 = (uint64_t) cc;
	cc = cc >> 64;
	cc += t2;
	t2 = (uint64_t) cc;
#if 0
	// not necessary with 2-bits guard
	cc = cc >> 64;
	uint64_t t3 = (uint64_t) cc;
	assert(t3 == 0);
#endif
#if PARANOID
	assert(cc >> 64 == 0);
#endif

	m = t0 * mmagic;	// #3
	cs = (uint128_t) m *mod_lo;	// #8
	cs += t0;
	cs = cs >> 64;
    
    cs += (uint128_t) m *mod_hi; // CAN OPTIMIZE
    

	cs += t1;
	t0 = (uint64_t) cs;
	cs = cs >> 64;
	cs += t2;
	t1 = (uint64_t) cs;
#if 0
	// not necessary with 2-bits guard
	cs = cs >> 64;
	cs += t3;
	t2 = (uint64_t) cs;
	assert(t2 == 0);
#endif
#if PARANOID
	assert(cs >> 64 == 0);
#endif

	*res_lo = t0;
	*res_hi = t1;

}

__host__ __device__ inline void ciosModSquare3_128(uint64_t * res_lo, uint64_t * res_hi, uint64_t mod_lo,
                                                   uint64_t mod_hi, uint64_t mmagic)
{
	ciosModSquare128(res_lo, res_hi, mod_lo, mod_hi, mmagic);
	ciosModSquare128(res_lo, res_hi, mod_lo, mod_hi, mmagic);
	ciosModSquare128(res_lo, res_hi, mod_lo, mod_hi, mmagic);
}

#ifdef HIGH_64
__host__ __device__ bool ciosFermatTest128(uint64_t n_lo) {
#else
__host__ __device__ bool ciosFermatTest128(uint64_t n_lo, uint64_t HIGH_64) {
#endif
#if PARANOID
	assert((n_lo & 1) == 1);
#endif
    //const uint64_t n_hi = <stuff here>;

	uint64_t res_lo, res_hi;
	uint64_t one_lo, one_hi;
	int bit;
	// constant -1/m mod 2^64
	uint64_t mmagic = montgomeryInverse64(n_lo);

	// enter montgomery domain
	// constant 2^128 mod m
	ciosConstants128(n_lo, HIGH_64, &one_lo, &one_hi);
	res_hi = one_hi;
	res_lo = one_lo;

    if (HIGH_64 == 0) {
        bit = 64 - my_clz64(n_lo);
        uint64_t msb_bits = bit < 5 ? bit - 1 : 3;
        uint64_t msb_mask = (1 << msb_bits) - 1;
        bit -= msb_bits;
        my_shld64(&res_hi, &res_lo, (n_lo >> bit) & msb_mask);

    } else {
        bit = 64 - my_clz64(HIGH_64);
        uint64_t msb_bits = bit < 4 ? bit : 3;
        uint64_t msb_mask = (1 << msb_bits) - 1;
        bit -= msb_bits;
        my_shld64(&res_hi, &res_lo, (HIGH_64 >> bit) & msb_mask);

        while (bit >= 3) {
            bit -= 3;
            // square and reduce
            ciosModSquare3_128(&res_lo, &res_hi, n_lo, HIGH_64, mmagic);
            // shift
            my_shld64(&res_hi, &res_lo, ((HIGH_64 >> bit) & 7));
        }

        while (bit) {
            bit -= 1;
            // square and reduce
            ciosModSquare128(&res_lo, &res_hi, n_lo, HIGH_64, mmagic);
            // shift
            my_shld64(&res_hi, &res_lo, ((HIGH_64 >> bit) & 1));
        }

        bit = 64;
    }
	//}
	while (bit >= 5) {
		bit -= 3;
		// square and reduce
		ciosModSquare3_128(&res_lo, &res_hi, n_lo, HIGH_64, mmagic);
		// shift
		my_shld64(&res_hi, &res_lo, ((n_lo >> bit) & 7));
	}

	while (bit > 1) {
		bit -= 1;
		// square and reduce
		ciosModSquare128(&res_lo, &res_hi, n_lo, HIGH_64, mmagic);
		// shift
		my_shld64(&res_hi, &res_lo, ((n_lo >> bit) & 1));
	}

	// make sure result is strictly less than the modulus
	ciosSubtract128(&res_lo, &res_hi, n_lo, HIGH_64);

	uint64_t legendre = ((n_lo >> 1) ^ (n_lo >> 2)) & 1;	// shortcut calculation of legendre symbol

	uint64_t m1_lo;
	uint64_t m1_hi;
	uint8_t c;
	c = my_sbb64(0, n_lo, one_lo, &m1_lo);
	my_sbb64(c, HIGH_64, one_hi, &m1_hi);

	return ((res_lo == (legendre ? m1_lo : one_lo)) && (res_hi == (legendre ? m1_hi : one_hi)));
}


// ciosFermatTest128 should be used for up to 119 bits
// montgomeryFermatTest128 should be used fro 120-127 bits



//       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
// ===== Thanks to Perig for this code ===== (end)
extern "C" __global__ void phase0_perig_reference(const uint64_t* lows,uint32_t* out,unsigned count,unsigned repeats,unsigned cacheMode){
 for(unsigned i=blockIdx.x*blockDim.x+threadIdx.x;i<count;i+=gridDim.x*blockDim.x)
  for(unsigned r=0;r<repeats;++r){
   const uint64_t low=reinterpret_cast<const volatile uint64_t*>(lows)[i];
   out[uint64_t(i)*repeats+r]=uint32_t(ciosFermatTest128(low));
  }
}
extern "C" __global__ void m600_same_euler_jacobi(const uint64_t* lows,uint32_t* out,unsigned count,unsigned repeats,unsigned cacheMode){
 pgn_stateful_u160::State state{};
 for(unsigned i=blockIdx.x*blockDim.x+threadIdx.x;i<count;i+=gridDim.x*blockDim.x)
  for(unsigned r=0;r<repeats;++r){
   const uint64_t low=reinterpret_cast<const volatile uint64_t*>(lows)[i];
   if(!cacheMode)state={}; // COLD: exact GPU buildJob paid for EVERY query.
   out[uint64_t(i)*repeats+r]=uint32_t(pgn_stateful_u160::test(low,state));
  }
}
