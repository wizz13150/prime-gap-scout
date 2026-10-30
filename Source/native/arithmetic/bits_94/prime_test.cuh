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
constexpr unsigned Bits = 94, High = 542101086, SuffixBits = 85, Groups = 42, Tail = 1,
                   SeedBits = 30, SeedFolds = 2, CacheBits = 126;
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
                 "mad.lo.cc.u32 l,q0,542101086,l;\n\t"
                 "madc.hi.u32 m,q0,542101086,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,542101086,l;\n\t"
                 "madc.hi.u32 m,q1,542101086,m;\n\t"
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
    hostAddProduct(l, m, h, q0, 542101086);
    hostAddProduct(l, m, h, a.x, 2 * a.z);
    hostAddProduct(l, m, h, q1, n1);
    hostAddProduct(l, m, h, a.y, a.y);
    t.x = l;
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q1, 542101086);
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
                 "mad.lo.cc.u32 l,q0,542101086,l;\n\t"
                 "madc.hi.u32 m,q0,542101086,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,542101086,l;\n\t"
                 "madc.hi.u32 m,q1,542101086,m;\n\t"
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
    hostAddProduct(l, m, h, q0, 542101086);
    hostAddProduct(l, m, h, a.x, 2 * a.z);
    hostAddProduct(l, m, h, q1, n1);
    hostAddProduct(l, m, h, a.y, a.y);
    t.x = l;
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q1, 542101086);
    hostAddProduct(l, m, h, a.y, 2 * a.z);
    t.y = l;
    const uint64_t top = uint64_t(a.z) * a.z + m;
    t.z = uint32_t(top);
    t.w = uint32_t(top >> 32);
#endif
    return t;
}

struct Quotient {
    uint32_t lo, hi;
};
WP_HD uint32_t inverse32(uint32_t n0) {
    uint32_t x = n0;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    return 0u - x;
}
WP_HD Value sub96(Value a, Value b) {
    uint64_t t = uint64_t(a.x) - b.x;
    Value r{uint32_t(t), 0, 0};
    t = uint64_t(a.y) - b.y - (t >> 63);
    r.y = uint32_t(t);
    r.z = a.z - b.z - uint32_t(t >> 63);
    return r;
}
WP_HD Wide shiftWide(Wide a, unsigned d) {
    uint64_t x = uint64_t(a.x) << d, y = (uint64_t(a.y) << d) | (x >> 32),
             z = (uint64_t(a.z) << d) | (y >> 32), w = (uint64_t(a.w) << d) | (z >> 32);
    return Wide{uint32_t(x), uint32_t(y), uint32_t(z), uint32_t(w)};
}
WP_HD Quotient quote34(Wide x, uint32_t mu) {
    uint64_t p01 = uint64_t(x.w) * mu + (uint64_t(x.z) * mu >> 32);
    uint64_t m = uint32_t(p01) + uint64_t(1) * x.z;
    uint64_t top = (p01 >> 32) + uint64_t(1) * x.w + (m >> 32);
    uint32_t middle = uint32_t(m), u = uint32_t(top), v = uint32_t(top >> 32);
    return Quotient{uint32_t((middle >> 30) | (u << 2)), uint32_t((u >> 30) | (v << 2))};
}
WP_HD Wide productQ(Quotient q, uint64_t low) {
    uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32);
    uint64_t a = uint64_t(q.lo) * n0, b = uint64_t(q.lo) * n1 + (a >> 32),
             c = uint64_t(q.lo) * High + (b >> 32);
    Wide p{uint32_t(a), uint32_t(b), uint32_t(c), uint32_t(c >> 32)};
    uint64_t t = uint64_t(p.y) + uint64_t(q.hi) * n0;
    p.y = uint32_t(t);
    t = uint64_t(p.z) + uint64_t(q.hi) * n1 + (t >> 32);
    p.z = uint32_t(t);
    p.w += uint32_t(uint64_t(q.hi) * High + (t >> 32));
    return p;
}
WP_HD Value normalize34(Wide x, uint64_t low, uint32_t mu) {
    Quotient q = quote34(x, mu);
    Wide p = productQ(q, low);
    return sub96(Value{x.x, x.y, x.z}, Value{p.x, p.y, p.z});
}
WP_HD int compareMu34(uint32_t lo, uint64_t low) {
    Wide p = productQ(Quotient{lo, 1}, low);
    // productQmod128 drops the fifthword; compute it explicitly for this cold compare.
    uint64_t a = uint64_t(lo) * uint32_t(low), b = uint64_t(lo) * uint32_t(low >> 32) + (a >> 32),
             c = uint64_t(lo) * High + (b >> 32);
    uint64_t t = uint32_t(b) + uint64_t(1) * uint32_t(low);
    t = uint32_t(c) + uint64_t(1) * uint32_t(low >> 32) + (t >> 32);
    t = (c >> 32) + uint64_t(1) * High + (t >> 32);
    uint32_t w4 = uint32_t(t >> 32), target4 = CacheBits == 128 ? 1u : 0u,
             target3 = CacheBits < 128 ? (uint32_t(1) << (CacheBits - 96)) : 0u;
    if (w4 != target4)
        return w4 < target4 ? -1 : 1;
    if (p.w != target3)
        return p.w < target3 ? -1 : 1;
    return (p.x | p.y | p.z) ? 1 : 0;
}
WP_HD uint32_t muFor(uint64_t low, State &s) {
    uint32_t tag = uint32_t(low >> 36);
    if (s.muLower && s.bucketTag == tag)
        return s.muLower;
    uint64_t end = (uint64_t(tag) << 36) | ((uint64_t(1) << 36) - 1);
    uint32_t lo = 0;
    WP_UNROLL for (int bit = 31; bit >= 0; --bit) {
        uint32_t q = lo | (uint32_t(1) << bit);
        if (compareMu34(q, end) <= 0)
            lo = q;
    }
    s.bucketTag = tag;
    s.muLower = lo;
    return lo;
}
WP_HD Value canonical(Value a, uint64_t low) {
    uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32);
    if (a.z > High || (a.z == High && (a.y > n1 || (a.y == n1 && a.x >= n0))))
        a = sub96(a, Value{n0, n1, High});
    return a;
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
WP_HD Value paidSeedFold125(Value a, uint32_t bits, uint32_t n0, uint32_t n1, uint32_t mu111Full) {
#if defined(__CUDA_ARCH__)
    Value d;
    asm volatile("{\n\t"
                 ".reg .u32 t0,t1,t2,t3,q,p0,p1,p2,r0,r1,r2;\n\t .reg .u64 column;\n\t"
                 "shl.b32 t0,%3,%6;\n\t shf.l.wrap.b32 t1,%3,%4,%6;\n\t"
                 "shf.l.wrap.b32 t2,%4,%5,%6;\n\t shf.l.wrap.b32 t3,%5,0,%6;\n\t"
                 "mul.hi.u32 p0,t2,%9;\n\t cvt.u64.u32 column,p0;\n\t"
                 "mad.wide.u32 column,t3,%9,column;\n\t"
                 "shr.u64 column,column,29;\n\t cvt.u32.u64 q,column;\n\t"
                 "mul.lo.u32 p0,q,%7;\n\t mul.hi.u32 p1,q,%7;\n\t"
                 "mad.lo.cc.u32 p1,q,%8,p1;\n\t madc.hi.u32 p2,q,%8,0;\n\t"
                 "mad.lo.u32 p2,q,542101086,p2;\n\t"
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
    const uint32_t q = uint32_t(column >> 29);
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
WP_HD Value makeSeed(uint64_t low, uint32_t muLo34) {
    uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32), muSeed = (1u << 31) | (muLo34 >> 1);
    Value a = subtract96(Value{0, 0, 0}, product32Low96(muSeed, low));
    WP_UNROLL for (unsigned i = 0; i < 2; ++i) a = paidSeedFold125(a, 30, n0, n1, muSeed);
    a = paidSeedFold125(a, 8, n0, n1, muSeed);
    return canonicalSeed(a, n0, n1);
}
WP_HD unsigned pairDigit(uint64_t low, unsigned group) {
    unsigned shift = 83 - 2 * group;
    if (shift >= 63)
        return (High >> (shift - 63)) & 3u;
    if (shift == 62)
        return unsigned(((High & 1u) << 1) | (low >> 63));
    return unsigned((low >> 1) >> shift) & 3u;
}
WP_HD bool terminal(Wide r, uint64_t low, unsigned digit, uint32_t np) {
    unsigned negative = ((low >> 1) ^ (low >> 2)) & 1u;
    uint32_t q = 0u - r.x * np;
    if (q > 1622454346)
        return false;
    Wide p = productQ(Quotient{q, 0}, low);
    uint64_t unit = digit ? (uint64_t(1) << (64 - digit)) : 0;
    uint32_t u0 = uint32_t(unit), u1 = uint32_t(unit >> 32), u2 = digit ? 0u : 1u;
    if (negative) {
        uint64_t t = uint64_t(p.x) - u0;
        p.x = uint32_t(t);
        t = uint64_t(p.y) - u1 - (t >> 63);
        p.y = uint32_t(t);
        t = uint64_t(p.z) - u2 - (t >> 63);
        p.z = uint32_t(t);
        p.w -= uint32_t(t >> 63);
    } else {
        uint64_t t = uint64_t(p.x) + u0;
        p.x = uint32_t(t);
        t = uint64_t(p.y) + u1 + (t >> 32);
        p.y = uint32_t(t);
        t = uint64_t(p.z) + u2 + (t >> 32);
        p.z = uint32_t(t);
        p.w += uint32_t(t >> 32);
    }
    return r.x == p.x && r.y == p.y && r.z == p.z && r.w == p.w;
}

#if defined(__CUDA_ARCH__)
__device__ __forceinline__ Value mu34FirstDevice(Value a, uint32_t n0, uint32_t n1, uint32_t np32,
                                                 uint32_t muL) {
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
                 "mad.lo.cc.u32 l,q0,542101086,l;\n\t"
                 "madc.hi.u32 m,q0,542101086,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,542101086,l;\n\t"
                 "madc.hi.u32 m,q1,542101086,m;\n\t"
                 "mad.lo.cc.u32 l,%4,z2,l;\n\t"
                 "madc.hi.u32 m,%4,z2,m;\n\t"
                 "mov.u32 t1,l;\n\t"
                 "mad.lo.cc.u32 t2,%5,%5,m;\n\t"
                 "madc.hi.u32 t3,%5,%5,0;\n\t"
                 "mul.hi.u32 p0,t2,%9;\n\t"
                 "mad.lo.cc.u32 p0,t3,%9,p0;\n\t"
                 "madc.hi.u32 p1,t3,%9,0;\n\t"
                 "add.cc.u32 p0,p0,t2;\n\t"
                 "addc.u32 p1,p1,t3;\n\t"
                 "shf.r.wrap.b32 q,p0,p1,30;\n\t"
                 "mul.lo.u32 p0,q,%6;\n\t"
                 "mul.hi.u32 p1,q,%6;\n\t"
                 "mad.lo.cc.u32 p1,q,%7,p1;\n\t"
                 "madc.hi.u32 p2,q,%7,0;\n\t"
                 "mad.lo.u32 p2,q,542101086,p2;\n\t"
                 "sub.cc.u32 %0,t0,p0;\n\t"
                 "subc.cc.u32 %1,t1,p1;\n\t"
                 "subc.u32 %2,t2,p2;\n\t"
                 "}\n"
                 : "=r"(d.x), "=r"(d.y), "=r"(d.z)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(n0), "r"(n1), "r"(np32), "r"(muL));
    return d;
}
#endif
WP_HD Value first34(Value a, uint32_t n0, uint32_t n1, uint32_t np, uint32_t mu) {
#if defined(__CUDA_ARCH__)
    return mu34FirstDevice(a, n0, n1, np, mu);
#else
    return normalize34(rawSquareWide(a, n0, n1, np), uint64_t(n0) | (uint64_t(n1) << 32), mu);
#endif
}
WP_HD Value last34(Wide a, unsigned digit, uint64_t low, uint32_t mu) {
#if defined(__CUDA_ARCH__)
    Value r;
    asm volatile("{\n\t .reg .u32 t0,t1,t2,t3,q,qh,p0,p1,p2;\n\t"
                 "shl.b32 t0,%3,%7;\n\t shf.l.wrap.b32 t1,%3,%4,%7;\n\t shf.l.wrap.b32 "
                 "t2,%4,%5,%7;\n\t shf.l.wrap.b32 t3,%5,%6,%7;\n\t"
                 "mul.hi.u32 p0,t2,%10;\n\t"
                 "mad.lo.cc.u32 p0,t3,%10,p0;\n\t"
                 "madc.hi.u32 p1,t3,%10,0;\n\t"
                 "add.cc.u32 p0,p0,t2;\n\t"
                 "addc.cc.u32 p1,p1,t3;\n\t"
                 "addc.u32 p2,0,0;\n\t"
                 "shf.r.wrap.b32 q,p0,p1,30;\n\t"
                 "shf.r.wrap.b32 qh,p1,p2,30;\n\t"
                 "mul.lo.u32 p0,q,%8;\n\t mul.hi.u32 p1,q,%8;\n\t mad.lo.cc.u32 p1,q,%9,p1;\n\t "
                 "madc.hi.u32 p2,q,%9,0;\n\t mad.lo.u32 p2,q,542101086,p2;\n\t"
                 ".reg .pred hasHigh;\n\t setp.ne.u32 hasHigh,qh,0;\n\t @hasHigh add.cc.u32 "
                 "p1,p1,%8;\n\t @hasHigh addc.u32 p2,p2,%9;\n\t"
                 "sub.cc.u32 %0,t0,p0;\n\t subc.cc.u32 %1,t1,p1;\n\t subc.u32 %2,t2,p2;\n\t}"
                 : "=r"(r.x), "=r"(r.y), "=r"(r.z)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(a.w), "r"(digit), "r"(uint32_t(low)),
                   "r"(uint32_t(low >> 32)), "r"(mu));
    return r;
#else
    return normalize34(shiftWide(a, digit), low, mu);
#endif
}
WP_HD bool test(uint64_t low, State &s) {
    if (!(low & 1u))
        return false;
    uint32_t mu = muFor(low, s), n0 = uint32_t(low), n1 = uint32_t(low >> 32), np = inverse32(n0);
    Value a = makeSeed(low, mu);
    WP_UNROLL for (unsigned g = 0; g < 42; ++g) {
        a = first34(a, n0, n1, np, mu);
        a = last34(rawSquareWide(a, n0, n1, np), pairDigit(low, g), low, mu);
    }

    return terminal(rawSquareWide(a, n0, n1, np), low, unsigned((low >> 1) & 1u), np);
}
} // namespace specialized_euler
#undef WP_HD
#undef WP_UNROLL
