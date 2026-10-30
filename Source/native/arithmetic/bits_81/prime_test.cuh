#pragma once
#include <stdint.h>
#ifdef __CUDACC__
#define WP_HD __host__ __device__ __forceinline__
#define WP_UNROLL _Pragma("unroll")
#else
#define WP_HD inline
#define WP_UNROLL
#endif
namespace specialized_euler {
struct Value {
    uint32_t x, y, z;
};
struct Wide {
    uint32_t x, y, z, w;
};
struct State {
    uint32_t bucketTag = 0, muLower = 0;
};
static_assert(sizeof(State) == 8, "Singlefullµ108State8");
constexpr unsigned Bits = 81, High = 108420, SuffixBits = 72, Groups = 36, Tail = 0, SeedBits = 30,
                   SeedFolds = 5, CacheBits = 112;
#if !defined(__CUDA_ARCH__)
WP_HD void hostAddProduct(uint32_t &l, uint32_t &m, uint32_t &h, uint32_t x, uint32_t y) {
    const uint64_t product = uint64_t(x) * y;
    uint64_t s = uint64_t(l) + uint32_t(product);
    l = uint32_t(s);
    s = uint64_t(m) + (product >> 32) + (s >> 32);
    m = uint32_t(s);
    h += uint32_t(s >> 32);
}
#endif
WP_HD Value rawSquareBounded(Value a, uint32_t n0, uint32_t n1, uint32_t np32) {
    Value t;
#if defined(__CUDA_ARCH__)
    asm volatile("{\n\t"
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
                 "mad.lo.cc.u32 l,q0,108420,l;\n\t"
                 "madc.hi.u32 m,q0,108420,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,108420,l;\n\t"
                 "madc.hi.u32 m,q1,108420,m;\n\t"
                 "mad.lo.cc.u32 l,%4,z2,l;\n\t"
                 "madc.hi.u32 m,%4,z2,m;\n\t"
                 "mov.u32 t1,l;\n\t"
                 "mad.lo.u32 t2,%5,%5,m;\n\t"
                 "mov.u32 %0,t0;\n\t"
                 "mov.u32 %1,t1;\n\t"
                 "mov.u32 %2,t2;\n\t"
                 "}\n"
                 : "=r"(t.x), "=r"(t.y), "=r"(t.z)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(n0), "r"(n1), "r"(np32));
#else
    // Portable column counterpart; independent integer oracle is proposed separately.

    const uint64_t xx = uint64_t(a.x) * a.x;
    uint32_t l = uint32_t(xx), m = uint32_t(xx >> 32), h = 0;
    const uint32_t q0 = l * np32;
    hostAddProduct(l, m, h, q0, n0);
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q0, n1);
    hostAddProduct(l, m, h, a.x, a.y);
    hostAddProduct(l, m, h, a.x, a.y);
    const uint32_t q1 = l * np32;
    hostAddProduct(l, m, h, q1, n0);
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q0, 108420);
    hostAddProduct(l, m, h, a.x, 2 * a.z);
    hostAddProduct(l, m, h, q1, n1);
    hostAddProduct(l, m, h, a.y, a.y);
    t.x = l;
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q1, 108420);
    hostAddProduct(l, m, h, a.y, 2 * a.z);
    t.y = l;
    t.z = a.z * a.z + m;
#endif
    return t;
}

WP_HD Wide rawSquareWide(Value a, uint32_t n0, uint32_t n1, uint32_t np32) {
    Wide t;
#if defined(__CUDA_ARCH__)
    asm volatile("{\n\t"
                 ".reg .u32 l,m,h,q0,q1,z2,t0,t1,t2,t3;\n\t"
                 "add.u32 z2,%6,%6;\n\t"
                 "mul.lo.u32 l,%4,%4;\n\t"
                 "mul.hi.u32 m,%4,%4;\n\t"
                 "mul.lo.u32 q0,l,%9;\n\t"
                 "mad.lo.cc.u32 l,q0,%7,l;\n\t"
                 "madc.hi.cc.u32 m,q0,%7,m;\n\t"
                 "addc.u32 h,0,0;\n\t"
                 "mov.u32 l,m;\n\t"
                 "mov.u32 m,h;\n\t"
                 "mad.lo.cc.u32 l,q0,%8,l;\n\t"
                 "madc.hi.u32 m,q0,%8,m;\n\t"
                 "mov.u32 h,0;\n\t"
                 "mad.lo.cc.u32 l,%4,%5,l;\n\t"
                 "madc.hi.cc.u32 m,%4,%5,m;\n\t"
                 "addc.u32 h,h,0;\n\t"
                 "mad.lo.cc.u32 l,%4,%5,l;\n\t"
                 "madc.hi.cc.u32 m,%4,%5,m;\n\t"
                 "addc.u32 h,h,0;\n\t"
                 "mul.lo.u32 q1,l,%9;\n\t"
                 "mad.lo.cc.u32 l,q1,%7,l;\n\t"
                 "madc.hi.cc.u32 m,q1,%7,m;\n\t"
                 "addc.u32 h,h,0;\n\t"
                 "mov.u32 l,m;\n\t"
                 "mov.u32 m,h;\n\t"
                 "mad.lo.cc.u32 l,q0,108420,l;\n\t"
                 "madc.hi.u32 m,q0,108420,m;\n\t"
                 "mad.lo.cc.u32 l,%4,z2,l;\n\t"
                 "madc.hi.u32 m,%4,z2,m;\n\t"
                 "mov.u32 h,0;\n\t"
                 "mad.lo.cc.u32 l,q1,%8,l;\n\t"
                 "madc.hi.cc.u32 m,q1,%8,m;\n\t"
                 "addc.u32 h,h,0;\n\t"
                 "mad.lo.cc.u32 l,%5,%5,l;\n\t"
                 "madc.hi.cc.u32 m,%5,%5,m;\n\t"
                 "addc.u32 h,h,0;\n\t"
                 "mov.u32 t0,l;\n\t"
                 "mov.u32 l,m;\n\t"
                 "mov.u32 m,h;\n\t"
                 "mad.lo.cc.u32 l,q1,108420,l;\n\t"
                 "madc.hi.u32 m,q1,108420,m;\n\t"
                 "mad.lo.cc.u32 l,%5,z2,l;\n\t"
                 "madc.hi.u32 m,%5,z2,m;\n\t"
                 "mov.u32 t1,l;\n\t"
                 "mad.lo.cc.u32 t2,%6,%6,m;\n\t"
                 "madc.hi.u32 t3,%6,%6,0;\n\t"
                 "mov.u32 %0,t0;\n\t"
                 "mov.u32 %1,t1;\n\t"
                 "mov.u32 %2,t2;\n\t"
                 "mov.u32 %3,t3;\n\t"
                 "}\n"
                 : "=r"(t.x), "=r"(t.y), "=r"(t.z), "=r"(t.w)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(n0), "r"(n1), "r"(np32));
#else
    // Portable column counterpart; independent integer oracle is proposed separately.

    const uint64_t xx = uint64_t(a.x) * a.x;
    uint32_t l = uint32_t(xx), m = uint32_t(xx >> 32), h = 0;
    const uint32_t q0 = l * np32;
    hostAddProduct(l, m, h, q0, n0);
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q0, n1);
    hostAddProduct(l, m, h, a.x, a.y);
    hostAddProduct(l, m, h, a.x, a.y);
    const uint32_t q1 = l * np32;
    hostAddProduct(l, m, h, q1, n0);
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q0, 108420);
    hostAddProduct(l, m, h, a.x, 2 * a.z);
    hostAddProduct(l, m, h, q1, n1);
    hostAddProduct(l, m, h, a.y, a.y);
    t.x = l;
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q1, 108420);
    hostAddProduct(l, m, h, a.y, 2 * a.z);
    t.y = l;
    const uint64_t top = uint64_t(a.z) * a.z + m;
    t.z = uint32_t(top);
    t.w = uint32_t(top >> 32);
#endif
    return t;
}
#if defined(__CUDA_ARCH__)
__device__ __forceinline__ Value normalizedFirstDevice(Value a, uint32_t n0, uint32_t n1,
                                                       uint32_t np32, uint32_t muL) {
    Value d;
    // One CC-local block. l/m/h are a column plus carry, not a 64-bit C++
    // comparison or carry materialisation. Small terms precede full products.
    asm volatile("{\n\t"
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
                 "mad.lo.cc.u32 l,q0,108420,l;\n\t"
                 "madc.hi.u32 m,q0,108420,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,108420,l;\n\t"
                 "madc.hi.u32 m,q1,108420,m;\n\t"
                 "mad.lo.cc.u32 l,%4,z2,l;\n\t"
                 "madc.hi.u32 m,%4,z2,m;\n\t"
                 "mov.u32 t1,l;\n\t"
                 "mad.lo.u32 t2,%5,%5,m;\n\t"
                 "mul.hi.u32 q,t2,%9;\n\t"
                 "mul.lo.u32 p0,q,%6;\n\t"
                 "mul.hi.u32 p1,q,%6;\n\t"
                 "mad.lo.cc.u32 p1,q,%7,p1;\n\t"
                 "madc.hi.u32 p2,q,%7,0;\n\t"
                 "mad.lo.u32 p2,q,108420,p2;\n\t"
                 "sub.cc.u32 %0,t0,p0;\n\t"
                 "subc.cc.u32 %1,t1,p1;\n\t"
                 "subc.u32 %2,t2,p2;\n\t"
                 "}\n"
                 : "=r"(d.x), "=r"(d.y), "=r"(d.z)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(n0), "r"(n1), "r"(np32), "r"(muL));
    return d;
}
#endif
WP_HD uint32_t negativeInverse32(uint32_t n0) {
    uint32_t x = n0;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    return 0u - x;
}
WP_HD Value product32Low96(uint32_t q, uint64_t low) {
    const uint64_t a = uint64_t(q) * uint32_t(low),
                   b = uint64_t(q) * uint32_t(low >> 32) + (a >> 32);
    return Value{uint32_t(a), uint32_t(b), uint32_t(uint64_t(q) * High + (b >> 32))};
}
WP_HD Value subtract96(Value a, Value p) {
#if defined(__CUDA_ARCH__)
    Value r;
    asm("{\n\t.reg .u32 x,y,z;\n\t sub.cc.u32 x,%3,%6;\n\t subc.cc.u32 y,%4,%7;\n\t subc.u32 "
        "z,%5,%8;\n\t mov.u32 %0,x;\n\t mov.u32 %1,y;\n\t mov.u32 %2,z;\n\t}"
        : "=r"(r.x), "=r"(r.y), "=r"(r.z)
        : "r"(a.x), "r"(a.y), "r"(a.z), "r"(p.x), "r"(p.y), "r"(p.z));
    return r;
#else
    uint64_t d = uint64_t(a.x) - p.x;
    Value r{uint32_t(d), 0, 0};
    d = uint64_t(a.y) - p.y - uint32_t(d >> 63);
    r.y = uint32_t(d);
    r.z = a.z - p.z - uint32_t(d >> 63);
    return r;
#endif
}
WP_HD Value normalizedFirst(Value a, uint32_t n0, uint32_t n1, uint32_t np, uint32_t mu96) {
#if defined(__CUDA_ARCH__)
    return normalizedFirstDevice(a, n0, n1, np, mu96);
#else
    Value x = rawSquareBounded(a, n0, n1, np);
    uint32_t q = uint32_t(uint64_t(x.z) * mu96 >> 32);
    return subtract96(x, product32Low96(q, uint64_t(n0) | (uint64_t(n1) << 32)));
#endif
}
WP_HD Value seedFold112Full(Value a, uint32_t bits, uint32_t n0, uint32_t n1, uint32_t mu111Full) {
#if defined(__CUDA_ARCH__)
    Value d;
    asm volatile("{\n\t"
                 ".reg .u32 t0,t1,t2,t3,q,p0,p1,p2,r0,r1,r2;\n\t .reg .u64 column;\n\t"
                 "shl.b32 t0,%3,%6;\n\t shf.l.wrap.b32 t1,%3,%4,%6;\n\t"
                 "shf.l.wrap.b32 t2,%4,%5,%6;\n\t shf.l.wrap.b32 t3,%5,0,%6;\n\t"
                 "mul.hi.u32 p0,t2,%9;\n\t cvt.u64.u32 column,p0;\n\t"
                 "mad.wide.u32 column,t3,%9,column;\n\t"
                 "shr.u64 column,column,16;\n\t cvt.u32.u64 q,column;\n\t"
                 "mul.lo.u32 p0,q,%7;\n\t mul.hi.u32 p1,q,%7;\n\t"
                 "mad.lo.cc.u32 p1,q,%8,p1;\n\t madc.hi.u32 p2,q,%8,0;\n\t"
                 "mad.lo.u32 p2,q,108420,p2;\n\t"
                 "sub.cc.u32 r0,t0,p0;\n\t subc.cc.u32 r1,t1,p1;\n\t subc.u32 r2,t2,p2;\n\t"
                 "mov.u32 %0,r0;\n\t mov.u32 %1,r1;\n\t mov.u32 %2,r2;\n\t}"
                 : "=r"(d.x), "=r"(d.y), "=r"(d.z)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(bits), "r"(n0), "r"(n1), "r"(mu111Full));
    return d;
#else
    const uint64_t x = uint64_t(a.x) << bits, y = (uint64_t(a.y) << bits) | (x >> 32),
                   z = (uint64_t(a.z) << bits) | (y >> 32);
    const Wide t{uint32_t(x), uint32_t(y), uint32_t(z), uint32_t(z >> 32)};
    const uint64_t column = (uint64_t(t.z) * mu111Full >> 32) + uint64_t(t.w) * mu111Full;
    const uint32_t q = uint32_t(column >> 16);
    const uint64_t p0 = uint64_t(q) * n0, p1 = uint64_t(q) * n1 + (p0 >> 32);
    const uint32_t p2 = uint32_t(uint64_t(q) * High + (p1 >> 32));
    uint64_t u = uint64_t(t.x) - uint32_t(p0);
    Value r{uint32_t(u), 0, 0};
    u = uint64_t(t.y) - uint32_t(p1) - uint32_t(u >> 63);
    r.y = uint32_t(u);
    r.z = t.z - p2 - uint32_t(u >> 63);
    return r;
#endif
}

WP_HD int compareProduct112Full(uint32_t q, uint64_t low) {
    const uint64_t a = uint64_t(q) * uint32_t(low),
                   b = uint64_t(q) * uint32_t(low >> 32) + (a >> 32),
                   c = uint64_t(q) * High + (b >> 32), target = uint64_t(65536) << 32;
    if (c < target)
        return -1;
    if (c > target)
        return 1;
    return (uint32_t(a) | uint32_t(b)) ? 1 : 0;
}
WP_HD uint32_t muFor(uint64_t low, State &s) {
    uint32_t tag = uint32_t(low >> 36);
    if (s.muLower && s.bucketTag == tag)
        return s.muLower;
    uint64_t last = (uint64_t(tag) << 36) | ((uint64_t(1) << 36) - 1);
    uint32_t mu = 0;
    WP_UNROLL for (int bit = 31; bit >= 0; --bit) {
        uint32_t q = mu | (uint32_t(1) << bit);
        if (compareProduct112Full(q, last) <= 0)
            mu = q;
    }
    s.bucketTag = tag;
    s.muLower = mu;
    return mu;
}
WP_HD Value canonicalSeed(Value a, uint32_t n0, uint32_t n1) {
    if (a.z > High || (a.z == High && (a.y > n1 || (a.y == n1 && a.x >= n0)))) {
        uint64_t t = uint64_t(a.x) - n0;
        a.x = uint32_t(t);
        t = uint64_t(a.y) - n1 - uint32_t(t >> 63);
        a.y = uint32_t(t);
        a.z -= High + uint32_t(t >> 63);
    }
    return a;
}
WP_HD Value lastFloatWide(Wide, unsigned, uint64_t, uint32_t);
WP_HD Value makeSeed(uint64_t low, uint32_t mu, uint32_t np, uint32_t coeff) {
    uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32);
    Value a = subtract96(Value{0, 0, 0}, product32Low96(mu, low));
    a = seedFold112Full(a, 30, n0, n1, mu);
    a = seedFold112Full(a, 27, n0, n1, mu);
    return lastFloatWide(rawSquareWide(a, n0, n1, np), 1, low, coeff);
}

WP_HD unsigned pairDigit(uint64_t low, unsigned group) {
    unsigned shift = 70 - 2 * group;
    if (shift >= 63)
        return (High >> (shift - 63)) & 3u;
    if (shift == 62)
        return unsigned(((High & 1u) << 1) | (low >> 63));
    return unsigned((low >> 1) >> shift) & 3u;
}

WP_HD Value shifted96(Value a, unsigned bits) {
#if defined(__CUDA_ARCH__)
    Value t;
    asm("{\n\t.reg .u32 x,y,z;\n\t shl.b32 x,%3,%6;\n\t shf.l.wrap.b32 y,%3,%4,%6;\n\t "
        "shf.l.wrap.b32 z,%4,%5,%6;\n\t mov.u32 %0,x;\n\t mov.u32 %1,y;\n\t mov.u32 %2,z;\n\t}"
        : "=r"(t.x), "=r"(t.y), "=r"(t.z)
        : "r"(a.x), "r"(a.y), "r"(a.z), "r"(bits));
    return t;
#else
    uint64_t x = uint64_t(a.x) << bits, y = (uint64_t(a.y) << bits) | (x >> 32),
             z = (uint64_t(a.z) << bits) | (y >> 32);
    return Value{uint32_t(x), uint32_t(y), uint32_t(z)};
#endif
}
WP_HD uint32_t lastQuotient(Value shifted, uint32_t mu) {
#if defined(__CUDA_ARCH__)
    return __umulhi(shifted.z, mu) >> 15;
#else
    return uint32_t((uint64_t(shifted.z) * mu) >> 47);
#endif
}
WP_HD Value lastFold111Full(Value a, unsigned bits, uint64_t low, uint32_t mu) {
#if defined(__CUDA_ARCH__)
    Value r;
    asm volatile(
        "{\n\t .reg .u32 t0,t1,t2,q,p0,p1,p2,x,y,z;\n\t"
        "shl.b32 t0,%3,%6;\n\t shf.l.wrap.b32 t1,%3,%4,%6;\n\t shf.l.wrap.b32 t2,%4,%5,%6;\n\t"
        "mul.hi.u32 q,t2,%9;\n\t shr.u32 q,q,15;\n\t"
        "mul.lo.u32 p0,q,%7;\n\t mul.hi.u32 p1,q,%7;\n\t mad.lo.cc.u32 p1,q,%8,p1;\n\t madc.hi.u32 "
        "p2,q,%8,0;\n\t mad.lo.u32 p2,q,108420,p2;\n\t"
        "sub.cc.u32 x,t0,p0;\n\t subc.cc.u32 y,t1,p1;\n\t subc.u32 z,t2,p2;\n\t mov.u32 %0,x;\n\t "
        "mov.u32 %1,y;\n\t mov.u32 %2,z;\n\t}"
        : "=r"(r.x), "=r"(r.y), "=r"(r.z)
        : "r"(a.x), "r"(a.y), "r"(a.z), "r"(bits), "r"(uint32_t(low)), "r"(uint32_t(low >> 32)),
          "r"(mu));
    return r;
#else
    Value t = shifted96(a, bits);
    return subtract96(t, product32Low96(lastQuotient(t, mu), low));
#endif
}
WP_HD Value lastFoldWide(Wide a, unsigned bits, uint64_t low, uint32_t mu) {
#if defined(__CUDA_ARCH__)
    Value r;
    asm volatile("{\n\t.reg .u32 t0,t1,t2,t3,q,p0,p1,p2,x,y,z; .reg .u64 col;\n\t"
                 "shl.b32 t0,%3,%7;\n\t shf.l.wrap.b32 t1,%3,%4,%7;\n\t shf.l.wrap.b32 "
                 "t2,%4,%5,%7;\n\t shf.l.wrap.b32 t3,%5,%6,%7;\n\t"
                 "mul.hi.u32 q,t2,%10;\n\t cvt.u64.u32 col,q;\n\t mad.wide.u32 col,t3,%10,col;\n\t "
                 "shr.u64 col,col,15;\n\t cvt.u32.u64 q,col;\n\t"
                 "mul.lo.u32 p0,q,%8;\n\t mul.hi.u32 p1,q,%8;\n\t mad.lo.cc.u32 p1,q,%9,p1;\n\t "
                 "madc.hi.u32 p2,q,%9,0;\n\t mad.lo.u32 p2,q,108420,p2;\n\t"
                 "sub.cc.u32 x,t0,p0;\n\t subc.cc.u32 y,t1,p1;\n\t subc.u32 z,t2,p2;\n\t mov.u32 "
                 "%0,x;\n\t mov.u32 %1,y;\n\t mov.u32 %2,z;\n\t}"
                 : "=r"(r.x), "=r"(r.y), "=r"(r.z)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(a.w), "r"(bits), "r"(uint32_t(low)),
                   "r"(uint32_t(low >> 32)), "r"(mu));
    return r;
#else
    uint64_t x = uint64_t(a.x) << bits, y = (uint64_t(a.y) << bits) | (x >> 32),
             z = (uint64_t(a.z) << bits) | (y >> 32), w = (uint64_t(a.w) << bits) | (z >> 32);
    uint64_t col = (uint64_t(uint32_t(z)) * mu >> 32) + uint64_t(uint32_t(w)) * mu;
    uint32_t q = uint32_t(col >> 15);
    return subtract96(Value{uint32_t(x), uint32_t(y), uint32_t(z)}, product32Low96(q, low));
#endif
}
constexpr uint32_t TerminalQMax = 212508u;
WP_HD uint32_t upper32Product(uint32_t x, uint32_t y) {
#if defined(__CUDA_ARCH__)
    return __umulhi(x, y);
#else
    return uint32_t((uint64_t(x) * y) >> 32);
#endif
}
// Return words1..3 of q*N + (negative?-1:+1)*2^(64-digit).
// Dividing the target by2^32 first leaves a safe33-bit shift, includingdigit0.
WP_HD Value terminalUpper(uint32_t q, uint64_t low, unsigned digit, unsigned negative) {
    const uint64_t p1 = uint64_t(q) * uint32_t(low >> 32) + upper32Product(q, uint32_t(low));
    const uint64_t p2 = uint64_t(q) * High + (p1 >> 32);
    const uint64_t t = uint64_t(1) << (32 - digit), mask = uint64_t(0) - negative,
                   delta = (t ^ mask) + negative;
    const uint32_t ext = 0u - negative;
    Value r;
#if defined(__CUDA_ARCH__)
    asm("{\n\t .reg .u32 r1,r2,r3;\n\t"
        "add.cc.u32 r1,%3,%6;\n\t addc.cc.u32 r2,%4,%7;\n\t addc.u32 r3,%5,%8;\n\t"
        "mov.u32 %0,r1;\n\t mov.u32 %1,r2;\n\t mov.u32 %2,r3;\n\t}"
        : "=r"(r.x), "=r"(r.y), "=r"(r.z)
        : "r"(uint32_t(p1)), "r"(uint32_t(p2)), "r"(uint32_t(p2 >> 32)), "r"(uint32_t(delta)),
          "r"(uint32_t(delta >> 32)), "r"(ext));
#else
    uint64_t u = uint64_t(uint32_t(p1)) + uint32_t(delta);
    r.x = uint32_t(u);
    u = uint64_t(uint32_t(p2)) + uint32_t(delta >> 32) + (u >> 32);
    r.y = uint32_t(u);
    r.z = uint32_t(p2 >> 32) + ext + uint32_t(u >> 32);
#endif
    return r;
}
WP_HD bool terminalEquation(Wide r, uint64_t low, unsigned digit, unsigned negative,
                            uint32_t np32) {
    if (digit > 3u || negative > 1u)
        return false;
    const uint32_t q = 0u - r.x * np32;
    if (q > TerminalQMax)
        return false;
    const Value p = terminalUpper(q, low, digit, negative);
    return r.y == p.x && r.z == p.y && r.w == p.z;
}

WP_HD uint32_t hostU64FloatRD(uint64_t x) {
    if (!x)
        return 0;
    int e = 63;
    while (!(x & (uint64_t(1) << e)))
        --e;
    uint32_t m = e > 23 ? uint32_t(x >> (e - 23)) : uint32_t(x << (23 - e));
    return (uint32_t(e + 127) << 23) | (m & 0x7fffffu);
}
WP_HD uint32_t hostMulFloatRD(uint32_t a, uint32_t b) {
    if (!a || !b)
        return 0;
    uint64_t p = uint64_t((a & 0x7fffffu) | (1u << 23)) * ((b & 0x7fffffu) | (1u << 23));
    int k = (p & (uint64_t(1) << 47)) ? 47 : 46,
        e = int((a >> 23) & 255) + int((b >> 23) & 255) - 300 + k;
    return (uint32_t(e + 127) << 23) | (uint32_t(p >> (k - 23)) & 0x7fffffu);
}
WP_HD uint32_t hostFloorFloat(uint32_t a) {
    if (!a)
        return 0;
    int e = int((a >> 23) & 255) - 127;
    if (e < 0)
        return 0;
    uint32_t m = (a & 0x7fffffu) | (1u << 23);
    return e < 23 ? m >> (23 - e) : m << (e - 23);
}
WP_HD uint32_t coefficientBits(uint32_t mu) {
#if defined(__CUDA_ARCH__)
    return __float_as_uint(__uint2float_rd(mu)) - (48u << 23);
#else
    return hostU64FloatRD(mu) - (48u << 23);
#endif
}
struct WideQuote {
    uint32_t zBits, pBits, q;
};
WP_HD WideQuote quoteWide(Wide a, uint32_t coeff) {
    WideQuote t{};
    uint64_t z = uint64_t(a.z) | (uint64_t(a.w) << 32);
#if defined(__CUDA_ARCH__)
    float f = __ull2float_rd(z);
    t.zBits = __float_as_uint(f);
    float p = __fmul_rd(f, __uint_as_float(coeff));
    t.pBits = __float_as_uint(p);
    t.q = __float2uint_rd(p);
#else
    t.zBits = hostU64FloatRD(z);
    t.pBits = hostMulFloatRD(t.zBits, coeff);
    t.q = hostFloorFloat(t.pBits);
#endif
    return t;
}
WP_HD Wide productWide(uint32_t q, uint64_t low) {
    uint64_t a = uint64_t(q) * uint32_t(low), b = uint64_t(q) * uint32_t(low >> 32) + (a >> 32),
             c = uint64_t(q) * High + (b >> 32);
    return Wide{uint32_t(a), uint32_t(b), uint32_t(c), uint32_t(c >> 32)};
}
WP_HD Wide shiftWide(Wide a, unsigned d) {
    uint64_t x = uint64_t(a.x) << d, y = (uint64_t(a.y) << d) | (x >> 32),
             z = (uint64_t(a.z) << d) | (y >> 32), w = (uint64_t(a.w) << d) | (z >> 32);
    return Wide{uint32_t(x), uint32_t(y), uint32_t(z), uint32_t(w)};
}
WP_HD Wide subtractWide(Wide a, Wide b) {
#if defined(__CUDA_ARCH__)
    Wide r;
    asm volatile("{\n\t sub.cc.u32 %0,%4,%8;\n\t subc.cc.u32 %1,%5,%9;\n\t subc.cc.u32 "
                 "%2,%6,%10;\n\t subc.u32 %3,%7,%11;\n\t}"
                 : "=r"(r.x), "=r"(r.y), "=r"(r.z), "=r"(r.w)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(a.w), "r"(b.x), "r"(b.y), "r"(b.z), "r"(b.w));
    return r;
#else
    uint64_t t = uint64_t(a.x) - b.x;
    Wide r{uint32_t(t), 0, 0, 0};
    t = uint64_t(a.y) - b.y - (t >> 63);
    r.y = uint32_t(t);
    t = uint64_t(a.z) - b.z - (t >> 63);
    r.z = uint32_t(t);
    r.w = a.w - b.w - uint32_t(t >> 63);
    return r;
#endif
}
WP_HD Wide normalizeWide(Wide a, uint64_t low, uint32_t coeff) {
    return subtractWide(a, productWide(quoteWide(a, coeff).q, low));
}
WP_HD Value narrow(Wide a) {
    return Value{a.x, a.y, a.z};
}

#if defined(__CUDA_ARCH__)
__device__ __forceinline__ Value normalizedWideFloatDevice(Value a, uint32_t n0, uint32_t n1,
                                                           uint32_t np32, uint32_t muL) {
    Value d;
    // One CC-local block. l/m/h are a column plus carry, not a 64-bit C++
    // comparison or carry materialisation. Small terms precede full products.
    asm volatile("{\n\t"
                 ".reg .u32 l,m,h,q0,q1,z2,t0,t1,t2,t3,q,p0,p1,p2;\n\t"
                 ".reg .u64 column;\n\t .reg .f32 fz,fc,fq;\n\t"
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
                 "mad.lo.cc.u32 l,q0,108420,l;\n\t"
                 "madc.hi.u32 m,q0,108420,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,108420,l;\n\t"
                 "madc.hi.u32 m,q1,108420,m;\n\t"
                 "mad.lo.cc.u32 l,%4,z2,l;\n\t"
                 "madc.hi.u32 m,%4,z2,m;\n\t"
                 "mov.u32 t1,l;\n\t"
                 "mad.lo.cc.u32 t2,%5,%5,m;\n\t"
                 "madc.hi.u32 t3,%5,%5,0;\n\t"
                 "mov.b64 column,{t2,t3};\n\t"
                 "cvt.rm.f32.u64 fz,column;\n\t mov.b32 fc,%9;\n\t"
                 "mul.rm.f32 fq,fz,fc;\n\t cvt.rmi.u32.f32 q,fq;\n\t"
                 "mul.lo.u32 p0,q,%6;\n\t"
                 "mul.hi.u32 p1,q,%6;\n\t"
                 "mad.lo.cc.u32 p1,q,%7,p1;\n\t"
                 "madc.hi.u32 p2,q,%7,0;\n\t"
                 "mad.lo.u32 p2,q,108420,p2;\n\t"
                 "sub.cc.u32 %0,t0,p0;\n\t"
                 "subc.cc.u32 %1,t1,p1;\n\t"
                 "subc.u32 %2,t2,p2;\n\t"
                 "}\n"
                 : "=r"(d.x), "=r"(d.y), "=r"(d.z)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(n0), "r"(n1), "r"(np32), "r"(muL));
    return d;
}
#endif
WP_HD Value normalizeNarrow(Wide a, uint64_t low, uint32_t coeff) {
    return subtract96(Value{a.x, a.y, a.z}, product32Low96(quoteWide(a, coeff).q, low));
}
WP_HD Value firstFloatWide(Value a, uint32_t n0, uint32_t n1, uint32_t np, uint32_t coeff) {
#if defined(__CUDA_ARCH__)
    return normalizedWideFloatDevice(a, n0, n1, np, coeff);
#else
    return normalizeNarrow(rawSquareWide(a, n0, n1, np), uint64_t(n0) | (uint64_t(n1) << 32),
                           coeff);
#endif
}
WP_HD Value lastFloatWide(Wide a, unsigned digit, uint64_t low, uint32_t coeff) {
#if defined(__CUDA_ARCH__)
    Value r;
    asm volatile(
        "{\n\t .reg .u32 t0,t1,t2,t3,q,p0,p1,p2;\n\t .reg .u64 zz;\n\t .reg .f32 fz,fc,fq;\n\t"
        "shl.b32 t0,%3,%7;\n\t shf.l.wrap.b32 t1,%3,%4,%7;\n\t shf.l.wrap.b32 t2,%4,%5,%7;\n\t "
        "shf.l.wrap.b32 t3,%5,%6,%7;\n\t"
        "mov.b64 zz,{t2,t3};\n\t cvt.rm.f32.u64 fz,zz;\n\t mov.b32 fc,%10;\n\t mul.rm.f32 "
        "fq,fz,fc;\n\t cvt.rmi.u32.f32 q,fq;\n\t"
        "mul.lo.u32 p0,q,%8;\n\t mul.hi.u32 p1,q,%8;\n\t mad.lo.cc.u32 p1,q,%9,p1;\n\t madc.hi.u32 "
        "p2,q,%9,0;\n\t mad.lo.u32 p2,q,108420,p2;\n\t"
        "sub.cc.u32 %0,t0,p0;\n\t subc.cc.u32 %1,t1,p1;\n\t subc.u32 %2,t2,p2;\n\t}"
        : "=r"(r.x), "=r"(r.y), "=r"(r.z)
        : "r"(a.x), "r"(a.y), "r"(a.z), "r"(a.w), "r"(digit), "r"(uint32_t(low)),
          "r"(uint32_t(low >> 32)), "r"(coeff));
    return r;
#else
    return normalizeNarrow(shiftWide(a, digit), low, coeff);
#endif
}
WP_HD bool test(uint64_t low, State &s) {
    if (!(low & 1u))
        return false;
    uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32), mu = muFor(low, s),
             np = negativeInverse32(n0), coeff = coefficientBits(mu);
    Value a = makeSeed(low, mu, np, coeff);
    WP_UNROLL for (unsigned g = 0; g < 35; ++g) {
        a = firstFloatWide(a, n0, n1, np, coeff);
        a = lastFloatWide(rawSquareWide(a, n0, n1, np), pairDigit(low, g), low, coeff);
    }
    a = firstFloatWide(a, n0, n1, np, coeff);
    Wide r = rawSquareWide(a, n0, n1, np);
    return terminalEquation(r, low, unsigned((low >> 1) & 3u),
                            unsigned(((low >> 1) ^ (low >> 2)) & 1u), np);
}
} // namespace specialized_euler
#undef WP_HD
#undef WP_UNROLL
