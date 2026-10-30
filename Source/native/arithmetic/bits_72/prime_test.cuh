#pragma once
#include <stdint.h>
// BASE941 SOURCE ONLY: whole68 envelope; no CPU/SDK/GPU qualification.
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
struct State {
    uint32_t bucketTag = 0, muLower = 0;
};
static_assert(sizeof(State) == 8, "retained State8 shape");
constexpr unsigned Bits = 72, High = 162, SuffixBits = 63, SeedBits = 23, SeedFolds = 7;
constexpr unsigned Groups = SuffixBits / 3, Tail = SuffixBits % 3;
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
                 "mad.lo.cc.u32 l,q0,162,l;\n\t"
                 "madc.hi.u32 m,q0,162,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,162,l;\n\t"
                 "madc.hi.u32 m,q1,162,m;\n\t"
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
    hostAddProduct(l, m, h, q0, 162);
    hostAddProduct(l, m, h, a.x, 2 * a.z);
    hostAddProduct(l, m, h, q1, n1);
    hostAddProduct(l, m, h, a.y, a.y);
    t.x = l;
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q1, 162);
    hostAddProduct(l, m, h, a.y, 2 * a.z);
    t.y = l;
    t.z = a.z * a.z + m;
#endif
    return t;
}

#if defined(__CUDA_ARCH__)
__device__ __forceinline__ Value normalizedDevice(Value a, uint32_t n0, uint32_t n1, uint32_t np32,
                                                  uint32_t muL) {
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
                 "mad.lo.cc.u32 l,q0,162,l;\n\t"
                 "madc.hi.u32 m,q0,162,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,162,l;\n\t"
                 "madc.hi.u32 m,q1,162,m;\n\t"
                 "mad.lo.cc.u32 l,%4,z2,l;\n\t"
                 "madc.hi.u32 m,%4,z2,m;\n\t"
                 "mov.u32 t1,l;\n\t"
                 "mad.lo.u32 t2,%5,%5,m;\n\t"
                 "mul.hi.u32 q,t2,%9;\n\t"
                 "mul.lo.u32 p0,q,%6;\n\t"
                 "mul.hi.u32 p1,q,%6;\n\t"
                 "mad.lo.cc.u32 p1,q,%7,p1;\n\t"
                 "madc.hi.u32 p2,q,%7,0;\n\t"
                 "mad.lo.u32 p2,q,162,p2;\n\t"
                 "sub.cc.u32 %0,t0,p0;\n\t"
                 "subc.cc.u32 %1,t1,p1;\n\t"
                 "subc.u32 %2,t2,p2;\n\t"
                 "}\n"
                 : "=r"(d.x), "=r"(d.y), "=r"(d.z)
                 : "r"(a.x), "r"(a.y), "r"(a.z), "r"(n0), "r"(n1), "r"(np32), "r"(muL));
    return d;
}
#endif
template <bool Carry97>
WP_HD Value shiftFold(Value a, uint32_t bits, uint32_t n0, uint32_t n1, uint32_t mu) {
    Value t;
    uint32_t carry = 0;
#if defined(__CUDA_ARCH__)
    // PTX SHF has defined zero-distance semantics. No bits==0 branch is
    // required: the concatenation [0,a.z]<<0 has a zero high word.
    if constexpr (Carry97) {
        asm("{\n\t.reg .u32 x,y,z,h;\n\t"
            "shl.b32 x,%4,%7;\n\tshf.l.wrap.b32 y,%4,%5,%7;\n\t"
            "shf.l.wrap.b32 z,%5,%6,%7;\n\tshf.l.wrap.b32 h,%6,0,%7;\n\t"
            "mov.u32 %0,x;\n\tmov.u32 %1,y;\n\tmov.u32 %2,z;\n\tmov.u32 %3,h;\n\t}"
            : "=r"(t.x), "=r"(t.y), "=r"(t.z), "=r"(carry)
            : "r"(a.x), "r"(a.y), "r"(a.z), "r"(bits));
    } else {
        asm("{\n\t.reg .u32 x,y,z;\n\t"
            "shl.b32 x,%3,%6;\n\tshf.l.wrap.b32 y,%3,%4,%6;\n\t"
            "shf.l.wrap.b32 z,%4,%5,%6;\n\t"
            "mov.u32 %0,x;\n\tmov.u32 %1,y;\n\tmov.u32 %2,z;\n\t}"
            : "=r"(t.x), "=r"(t.y), "=r"(t.z)
            : "r"(a.x), "r"(a.y), "r"(a.z), "r"(bits));
    }
    Value d;
    asm("{\n\t.reg .u32 q,p0,p1,p2,r0,r1,r2;\n\t"
        "mul.hi.u32 q,%5,%8;\n\t"
        "mad.lo.u32 q,%9,%8,q;\n\t"
        "mul.lo.u32 p0,q,%6;\n\tmul.hi.u32 p1,q,%6;\n\t"
        "mad.lo.cc.u32 p1,q,%7,p1;\n\tmadc.hi.u32 p2,q,%7,0;\n\t"
        "mad.lo.u32 p2,q,162,p2;\n\t"
        "sub.cc.u32 r0,%3,p0;\n\tsubc.cc.u32 r1,%4,p1;\n\tsubc.u32 r2,%5,p2;\n\t"
        "mov.u32 %0,r0;\n\tmov.u32 %1,r1;\n\tmov.u32 %2,r2;\n\t}"
        : "=r"(d.x), "=r"(d.y), "=r"(d.z)
        : "r"(t.x), "r"(t.y), "r"(t.z), "r"(n0), "r"(n1), "r"(mu), "r"(carry));
    return d;
#else
    // The portable words use64-bit temporaries, so bits==0 never causes a
    // C++ shift by32; the high temporary carries the extra97th bit exactly.
    const uint64_t x = uint64_t(a.x) << bits;
    const uint64_t y = (uint64_t(a.y) << bits) | (x >> 32);
    const uint64_t highShift = (uint64_t(a.z) << bits) | (y >> 32);
    t = {uint32_t(x), uint32_t(y), uint32_t(highShift)};
    if constexpr (Carry97)
        carry = uint32_t(highShift >> 32);
    const uint32_t q = uint32_t((uint64_t(t.z) * mu) >> 32) + carry * mu;
    const uint64_t p0 = uint64_t(q) * n0;
    const uint64_t p1 = uint64_t(q) * n1 + (p0 >> 32);
    const uint32_t p2 = uint32_t(uint64_t(q) * 162 + (p1 >> 32));
    uint64_t z = uint64_t(t.x) - uint32_t(p0);
    Value d{uint32_t(z), 0, 0};
    z = uint64_t(t.y) - uint32_t(p1) - uint32_t(z >> 63);
    d.y = uint32_t(z);
    d.z = t.z - p2 - uint32_t(z >> 63);
    return d;
#endif
}

WP_HD uint32_t negativeInverse32(uint32_t n0) {
    uint32_t x = n0;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    x *= 2u - n0 * x;
    return 0u - x;
}
WP_HD int compareProduct96(uint32_t q, uint64_t low) {
    const uint64_t p0 = uint64_t(q) * uint32_t(low);
    const uint64_t p1 = uint64_t(q) * uint32_t(low >> 32) + (p0 >> 32);
    const uint64_t p2 = uint64_t(q) * High + (p1 >> 32);
    if (p2 < (uint64_t(1) << 32))
        return -1;
    if (p2 > (uint64_t(1) << 32))
        return 1;
    return (uint32_t(p0) | uint32_t(p1)) ? 1 : 0;
}
constexpr int muTopBit() {
    uint32_t q = UINT32_MAX / High;
    int b = -1;
    while (q) {
        ++b;
        q >>= 1;
    }
    return b;
}
constexpr int CoefficientTopBit = muTopBit();
WP_HD uint32_t muFor(uint64_t low, State &state) {
    const uint32_t tag = uint32_t(low >> 36);
    if (state.muLower && state.bucketTag == tag)
        return state.muLower;
    const uint64_t last = (uint64_t(tag) << 36) | ((uint64_t(1) << 36) - 1);
    uint32_t mu = 0;
    // Exact full-bucket coefficient. No float or new external per-N state.
    WP_UNROLL for (int bit = CoefficientTopBit; bit >= 0; --bit) {
        const uint32_t candidate = mu | (uint32_t(1) << bit);
        if (compareProduct96(candidate, last) <= 0)
            mu = candidate;
    }
    state.bucketTag = tag;
    state.muLower = mu;
    return mu;
}
WP_HD Value normalizedSquare(Value a, uint32_t n0, uint32_t n1, uint32_t np, uint32_t mu) {
#if defined(__CUDA_ARCH__)
    return normalizedDevice(a, n0, n1, np, mu);
#else
    return shiftFold<false>(rawSquareBounded(a, n0, n1, np), 0, n0, n1, mu);
#endif
}
WP_HD bool equal(Value a, Value b) {
    return a.x == b.x && a.y == b.y && a.z == b.z;
}
WP_HD Value canonicalSeed(Value a, uint32_t n0, uint32_t n1) {
    if (a.z > High || (a.z == High && (a.y > n1 || (a.y == n1 && a.x >= n0)))) {
        uint64_t d = uint64_t(a.x) - n0;
        a.x = uint32_t(d);
        d = uint64_t(a.y) - n1 - uint32_t(d >> 63);
        a.y = uint32_t(d);
        a.z -= High + uint32_t(d >> 63);
    }
    return a;
}
template <unsigned Bits = SuffixBits> WP_HD unsigned prefix(uint64_t low) {
    if constexpr (Bits == 63)
        return High;
    else
        return (High << (63 - Bits)) | unsigned(low >> (Bits + 1));
}
WP_HD Value makeSeed(uint64_t low, uint32_t n0, uint32_t n1, uint32_t mu) {
    Value a{0, 0, 1};
    WP_UNROLL for (unsigned i = 0; i < SeedFolds; ++i) a =
        shiftFold<false>(a, SeedBits, n0, n1, mu);
    a = shiftFold<false>(a, prefix(low) - SeedBits * SeedFolds, n0, n1, mu);
    // Seed folds preserve <2N. A single subtract publishes a<N at orbit entry.
    return canonicalSeed(a, n0, n1);
}
WP_HD Value residue(uint64_t low, uint32_t mu) {
    const uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32), np = negativeInverse32(n0);
    Value a = makeSeed(low, n0, n1, mu);
    const uint64_t exponent = low >> 1;
    WP_UNROLL for (unsigned group = 0; group < Groups; ++group) {
        a = rawSquareBounded(a, n0, n1, np);
        a = normalizedSquare(a, n0, n1, np, mu);
        a = rawSquareBounded(a, n0, n1, np);
        a = shiftFold<false>(a, uint32_t((exponent >> (SuffixBits - 3 - 3 * group)) & 7), n0, n1,
                             mu);
    }
    if constexpr (Tail == 1) {
        a = rawSquareBounded(a, n0, n1, np);
        a = shiftFold<false>(a, uint32_t(exponent & 1), n0, n1, mu);
    } else if constexpr (Tail == 2) {
        a = rawSquareBounded(a, n0, n1, np);
        a = normalizedSquare(a, n0, n1, np, mu);
        a = shiftFold<false>(a, uint32_t(exponent & 3), n0, n1, mu);
    }
    return a;
}
WP_HD bool verdict(Value a, uint64_t low) {
    const uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32);
    if (((low >> 1) ^ (low >> 2)) & 1u)
        return equal(a, Value{n0, n1, High - 1}) ||
               equal(a, Value{n0 << 1, uint32_t((low << 1) >> 32),
                              2 * High - 1 + uint32_t(low >> 63)});
    return equal(a, Value{0, 0, 1}) || equal(a, Value{n0, n1, High + 1});
}
WP_HD bool test(uint64_t low, State &state) {
    if (!(low & 1))
        return false;
    return verdict(residue(low, muFor(low, state)), low);
}
} // namespace specialized_euler
#undef WP_HD
#undef WP_UNROLL
