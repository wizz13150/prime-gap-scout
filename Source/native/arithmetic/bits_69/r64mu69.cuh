#pragma once
#include <stdint.h>
#include "raw69.cuh"
#ifdef __CUDACC__
#define R69_HD __host__ __device__ __forceinline__
#else
#define R69_HD inline
#endif
namespace cached_euler69 {
using Value = root69_raw::Value;
struct State {
    uint64_t anchor = 0;
    uint32_t mu = 0, ready = 0;
};
R69_HD uint32_t inverse(uint32_t n) {
    uint32_t x = n;
    x *= 2u - n * x;
    x *= 2u - n * x;
    x *= 2u - n * x;
    x *= 2u - n * x;
    return 0u - x;
}
R69_HD int compare(uint32_t q, uint64_t low) {
    const uint64_t p0 = uint64_t(q) * uint32_t(low),
                   p1 = uint64_t(q) * uint32_t(low >> 32) + (p0 >> 32),
                   p2 = uint64_t(q) * 21u + (p1 >> 32);
    if (p2 < (1ull << 32))
        return -1;
    if (p2 > (1ull << 32))
        return 1;
    return (uint32_t(p0) | uint32_t(p1)) ? 1 : 0;
}
R69_HD uint32_t muFor(uint64_t low, State &state) {
    const uint64_t anchor = low & ~((1ull << 36) - 1);
    if (state.ready == 0x6936344du && state.anchor == anchor)
        return state.mu;
    const uint64_t maximum = anchor | ((1ull << 36) - 1);
    uint32_t mu = 0;
#pragma unroll
    for (int bit = 27; bit >= 0; --bit) {
        const uint32_t candidate = mu | (1u << bit);
        if (compare(candidate, maximum) <= 0)
            mu = candidate;
    }
    state.anchor = anchor;
    state.mu = mu;
    state.ready = 0x6936344du;
    return mu;
}
#if !defined(__CUDA_ARCH__)
R69_HD void hostAddProduct(uint32_t &l, uint32_t &m, uint32_t &h, uint32_t x, uint32_t y) {
    const uint64_t product = uint64_t(x) * y;
    uint64_t s = uint64_t(l) + uint32_t(product);
    l = uint32_t(s);
    s = uint64_t(m) + (product >> 32) + (s >> 32);
    m = uint32_t(s);
    h += uint32_t(s >> 32);
}
R69_HD Value hostSquare(Value a, uint32_t n0, uint32_t n1, uint32_t np, uint32_t mu) {
    const uint64_t xx = uint64_t(a.x) * a.x;
    uint32_t l = uint32_t(xx), m = uint32_t(xx >> 32), h = 0;
    const uint32_t q0 = l * np;
    hostAddProduct(l, m, h, q0, n0);
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q0, n1);
    hostAddProduct(l, m, h, a.x, a.y);
    hostAddProduct(l, m, h, a.x, a.y);
    const uint32_t q1 = l * np;
    hostAddProduct(l, m, h, q1, n0);
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q0, 21);
    hostAddProduct(l, m, h, a.x, 2 * a.z);
    hostAddProduct(l, m, h, q1, n1);
    hostAddProduct(l, m, h, a.y, a.y);
    const uint32_t t0 = l;
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q1, 21);
    hostAddProduct(l, m, h, a.y, 2 * a.z);
    const uint32_t t1 = l, t2 = a.z * a.z + m, q = uint32_t(uint64_t(t2) * mu >> 32);
    const uint64_t p0 = uint64_t(q) * n0, p1 = uint64_t(q) * n1 + (p0 >> 32);
    uint64_t s = uint64_t(t0) - uint32_t(p0);
    Value d{uint32_t(s), 0, 0};
    s = uint64_t(t1) - uint32_t(p1) - uint32_t(s >> 63);
    d.y = uint32_t(s);
    d.z = t2 - (21 * q + uint32_t(p1 >> 32)) - uint32_t(s >> 63);
    return d;
}
#endif
R69_HD Value square(Value a, uint32_t n0, uint32_t n1, uint32_t np, uint32_t mu) {
#if defined(__CUDA_ARCH__)
    return root69_raw::square(a, n0, n1, np, mu);
#else
    return hostSquare(a, n0, n1, np, mu);
#endif
}
R69_HD Value rawSquare45(Value a, uint32_t n0, uint32_t n1, uint32_t np32) {
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
                 "mad.lo.cc.u32 l,q0,21,l;\n\t"
                 "madc.hi.u32 m,q0,21,m;\n\t"
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
                 "mad.lo.cc.u32 l,q1,21,l;\n\t"
                 "madc.hi.u32 m,q1,21,m;\n\t"
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
    // Portable host arithmetic counterpart, NOT separately compiled here.

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
    hostAddProduct(l, m, h, q0, 21);
    hostAddProduct(l, m, h, a.x, 2 * a.z);
    hostAddProduct(l, m, h, q1, n1);
    hostAddProduct(l, m, h, a.y, a.y);
    t.x = l;
    l = m;
    m = h;
    h = 0;
    hostAddProduct(l, m, h, q1, 21);
    hostAddProduct(l, m, h, a.y, 2 * a.z);
    t.y = l;
    t.z = a.z * a.z + m;
#endif
    return t;
}

template <bool Carry97>
R69_HD Value shiftFold(Value a, uint32_t bits, uint32_t n0, uint32_t n1, uint32_t mu) {
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
        "mad.lo.u32 p2,q,21,p2;\n\t"
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
    const uint32_t p2 = uint32_t(uint64_t(q) * 21 + (p1 >> 32));
    uint64_t z = uint64_t(t.x) - uint32_t(p0);
    Value d{uint32_t(z), 0, 0};
    z = uint64_t(t.y) - uint32_t(p1) - uint32_t(z >> 63);
    d.y = uint32_t(z);
    d.z = t.z - p2 - uint32_t(z >> 63);
    return d;
#endif
}

R69_HD Value shift(Value a, unsigned bits) {
    if (!bits)
        return a;
    return {a.x << bits, (a.y << bits) | (a.x >> (32 - bits)),
            (a.z << bits) | (a.y >> (32 - bits))};
}
R69_HD Value shiftReduce(Value a, unsigned bits, uint32_t n0, uint32_t n1, uint32_t mu) {
    if (!bits)
        return a;
    const Value t = shift(a, bits);
    const uint32_t q = uint32_t(uint64_t(t.z) * mu >> 32);
    const uint64_t p0 = uint64_t(q) * n0, p1 = uint64_t(q) * n1 + (p0 >> 32);
    uint64_t s = uint64_t(t.x) - uint32_t(p0);
    Value out{uint32_t(s), 0, 0};
    s = uint64_t(t.y) - uint32_t(p1) - uint32_t(s >> 63);
    out.y = uint32_t(s);
    out.z = t.z - (21u * q + uint32_t(p1 >> 32)) - uint32_t(s >> 63);
    return out;
}
R69_HD Value residue(uint64_t low, uint32_t mu) {
    const uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32), np = inverse(n0);
    Value a{0, 0, 1};
#pragma unroll
    for (unsigned i = 0; i < 6; ++i)
        a = shiftReduce(a, 26, n0, n1, mu);
    a = shiftReduce(a, 12u + uint32_t(low >> 61), n0, n1, mu);
    uint64_t stream = low << 3;
#if defined(__CUDA_ARCH__)
#pragma unroll
#endif
    for (unsigned i = 0; i < 15; ++i) {
        a = cached_euler69::rawSquare45(a, n0, n1,
                                        np); // <353N, explicit new private reduced-square admission
        a = cached_euler69::square(a, n0, n1, np, mu);  // <1.063N, exact same columns; raw96 fits
        a = cached_euler69::rawSquare45(a, n0, n1, np); // <25.84N, safely inside45N
        a = cached_euler69::rawSquare45(a, n0, n1, np); // <raw4*N
        a = cached_euler69::shiftFold<true>(a, uint32_t(stream >> 60), n0, n1,
                                            mu); // carry is FULL high word, not Boolean
        stream <<= 4;
    }
    const Value twoN{n0 << 1, (n1 << 1) | (n0 >> 31), 42u + uint32_t(low >> 63)};
    const bool ge =
        a.z > twoN.z || (a.z == twoN.z && (a.y > twoN.y || (a.y == twoN.y && a.x >= twoN.x)));
    if (ge) {
        uint64_t t = uint64_t(a.x) - twoN.x;
        a.x = uint32_t(t);
        t = uint64_t(a.y) - twoN.y - uint32_t(t >> 63);
        a.y = uint32_t(t);
        a.z -= twoN.z + uint32_t(t >> 63);
    }
    return a;
}

R69_HD bool same(Value a, Value b) {
    return a.x == b.x && a.y == b.y && a.z == b.z;
}
R69_HD bool test(uint64_t low, State &state) {
    if (!(low & 1u))
        return false;
    const auto a = residue(low, muFor(low, state));
    const uint32_t n0 = uint32_t(low), n1 = uint32_t(low >> 32);
    if (((low >> 1) ^ (low >> 2)) & 1u)
        return same(a, Value{n0, n1, 20}) ||
               same(a, Value{n0 << 1, uint32_t((low << 1) >> 32), 41u + uint32_t(low >> 63)});
    return same(a, Value{0, 0, 1}) || same(a, Value{n0, n1, 22});
}
} // namespace cached_euler69
#undef R69_HD
