#pragma once
#include <stdint.h>
#include "R64lazy32-67.cuh"

// C21 component SOURCE, no full-consumer compile/GPU/Native qualification.
// C21 proof extends the UNCHANGED C20 implementation to input<256*N.
// Only the implicit-high10 parent domain is supported; not arbitrary 68bits.
namespace root67_prp {
using root67_r64::Value;
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
    const uint64_t p2 = uint64_t(q)*5u+(p1>>32);
    if (p2 < (1ULL<<32)) return -1;
    if (p2 > (1ULL<<32)) return 1;
    return (uint32_t(p0)|uint32_t(p1)) ? 1 : 0;
}

// COLD perjob. Caller supplies the full actual query/halo envelope, NOT only
// owned output positions. Both endpoint highs must be10 and cannot wrap.
C21_HD JobMu buildJob(uint32_t highMin, uint64_t minLow,
                       uint32_t highMax, uint64_t maxLow) {
    JobMu out{minLow,maxLow,0,0};
    if (highMin!=5 || highMax!=5 || maxLow<minLow ||
        maxLow-minLow > (1ULL<<34)) return out;
    uint32_t mu=0;
    // N>10R implies quotient<2^29. Cold29-bit exact search, not perpoint.
    for (int bit=29;bit>=0;--bit) {
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
    hostAddProduct(l,m,h,q0,5);
    hostAddProduct(l,m,h,a.x,2*a.z);
    hostAddProduct(l,m,h,q1,n1);hostAddProduct(l,m,h,a.y,a.y);
    const uint32_t t0=l;l=m;m=h;h=0;
    hostAddProduct(l,m,h,q1,5);hostAddProduct(l,m,h,a.y,2*a.z);
    const uint32_t t1=l,t2=a.z*a.z+m,q=uint32_t(uint64_t(t2)*mu>>32);
    const uint64_t p0=uint64_t(q)*n0,p1=uint64_t(q)*n1+(p0>>32);
    uint64_t s=uint64_t(t0)-uint32_t(p0);Value d{uint32_t(s),0,0};
    s=uint64_t(t1)-uint32_t(p1)-uint32_t(s>>63);d.y=uint32_t(s);
    d.z=t2-(5*q+uint32_t(p1>>32))-uint32_t(s>>63);
    return d;
}
#endif

C21_HD Value squareAfterW3(Value a,uint32_t n0,uint32_t n1,uint32_t np,uint32_t mu) {
#if defined(__CUDA_ARCH__)
    return root67_r64::square(a,n0,n1,np,mu);
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
        "mad.lo.u32 p2,q,5,p2;\n\t"
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
    d.z=t.z-(5*q+uint32_t(p1>>32))-uint32_t(s>>63);
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


#undef C21_HD
#undef C21_UNROLL
} // root67_prp
