#ifndef PGN_CONDITIONAL_WALK_CUH
#define PGN_CONDITIONAL_WALK_CUH

// Conditional GPU search pipeline. Two bitmap slots
// alternate: mark(i+1) and walk(i) are independent; advance waits for BOTH.
// Every descriptor has a distinct retained result/stat slot, so no result is
// overwritten while the host verifies it after the complete graph job.
#include "candidate_walk.cuh"
#include "segmented_sieve.cuh"
#ifdef PGN_VERIFY_GAPS
#include "pgn_mr96.cuh"
#endif
#if !defined(PGN_FUSED_SIEVE) || !defined(PGN_EULER96) || !defined(PGN_EULER96_FIXED_HIGH10)
#error Finite conditional adapter requires the paid fused fixed-high-10 arithmetic
#endif
#ifndef PGN_DESCRIPTOR_LANES
#define PGN_DESCRIPTOR_LANES 2
#endif
constexpr unsigned PgnDescriptorLanes = PGN_DESCRIPTOR_LANES;
constexpr unsigned PgnBitmapSlots = 2 * PgnDescriptorLanes;
static_assert(PgnDescriptorLanes == 2 || PgnDescriptorLanes == 4 || PgnDescriptorLanes == 8 ||
                  PgnDescriptorLanes == 16 || PgnDescriptorLanes == 32 || PgnDescriptorLanes == 64,
              "Finite lane candidates only");
struct PgnWalkDescriptor {
    uint64_t low, high;
    uint32_t bitmap_blocks, owned_blocks;
};
struct PgnClass30Origin {
    uint64_t low, high;
};
__device__ __forceinline__ PgnClass30Origin pgn_class30_origin(PgnWalkDescriptor descriptor) {
    const uint64_t remainder = (descriptor.low % 30 + (descriptor.high % 30) * 16) % 30;
    return {descriptor.low - remainder, descriptor.high - (descriptor.low < remainder ? 1 : 0)};
}
struct PgnWalkGraphState {
    uint32_t cursor, count, completed;
};
struct PgnWalkGraphBuffers {
    const uint64_t *primes, *invp, *r64;
    const uint32_t *item_pidx, *item_k0, *wheel_primes, *window_steps;
    uint32_t item_count, gap_min, result_capacity, blocks_per_slot;
    uint64_t *bitmaps;
    w_gaprec_t *results;
    unsigned long long *stats;
#ifdef PGN_VERIFY_GAPS
    unsigned *proofs;
#endif
    const uint32_t *root_steps;
};
__global__ __maxnreg__(48) void pgn_graph_mark(const PgnWalkDescriptor *descriptors,
                                               const PgnWalkGraphState *state,
                                               PgnWalkGraphBuffers buffers, uint32_t ahead) {
    const uint32_t index = state->cursor + ahead;
    // The predicate is uniform for the entire CTA, before any shared barrier.
    if (index >= state->count)
        return;
    const PgnWalkDescriptor descriptor = descriptors[index];

    // Keep the descriptor cursor separate from the sieve's class-30 base.
    // 2^64 mod30=16; rounding a sieve must not redefine reporting ownership.
    const auto origin = pgn_class30_origin(descriptor);
    constexpr uint64_t words = (1ULL << 28) / 64;
    auto *bitmap =
        buffers.bitmaps + uint64_t(index % PgnBitmapSlots) * buffers.blocks_per_slot * words;
    // Repartition eachbitmap into16 contiguous32-tile cohorts; stride1 root reuse.
    // A bounded physical grid finishes dispatch quickly, leaving capacity for
    // already-ready walk/control kernels. Every CTA loop is uniform and finite.
    for (unsigned job = blockIdx.x; job < 16u * descriptor.bitmap_blocks; job += gridDim.x) {
        const unsigned cohort = job % 16u, logicalY = job / 16u;
        const uint64_t displacement = uint64_t(cohort) * 32u * ((1ULL << 19) / 8) * 30u;
        const uint64_t low = origin.low + displacement;
        const uint64_t high = origin.high + uint64_t(low < origin.low);
        // Contiguous32-tile ownership; all16cohorts cover exactly512tiles.
        segmented_sieve::body<true, true, true, true>(
            buffers.primes, buffers.invp, buffers.r64, buffers.item_pidx, buffers.item_k0,
            buffers.item_count, low, high, 1ULL << 19, 32, bitmap + uint64_t(cohort) * 32u * 8192u,
            8192, buffers.wheel_primes, 1, buffers.root_steps, 0, logicalY, 1);
        __syncthreads();
    }
}
__global__ __maxnreg__(40) void pgn_graph_walk(const PgnWalkDescriptor *descriptors,
                                               const PgnWalkGraphState *state,
                                               PgnWalkGraphBuffers buffers) {
    const uint32_t index = state->cursor;
    if (index >= state->count)
        return;
    const PgnWalkDescriptor descriptor = descriptors[index];
    const auto origin = pgn_class30_origin(descriptor);
    __shared__ uint32_t classes[8];
    __shared__ uint64_t batch_quotient;
    const uint64_t words = uint64_t(descriptor.bitmap_blocks) * ((1ULL << 28) / 64);
    if (threadIdx.x < 8)
        classes[threadIdx.x] = c30_cls[threadIdx.x];
#ifdef PGN_EULER96_BATCH_Q
    if (threadIdx.x == 0)
        batch_quotient = pgn_euler96::batchQuotient(origin.low, origin.high, words);
#else
    if (threadIdx.x == 0)
        batch_quotient = 0;
#endif
    __syncthreads();
    const auto *bitmap = buffers.bitmaps + uint64_t(index % PgnBitmapSlots) *
                                               buffers.blocks_per_slot * ((1ULL << 28) / 64);
    // Same ownership, Euler arithmetic and collective population as the paid
    // fixed-high-10 walk. This adapter deliberately rejects other high words.
    w_owned_slice<3, 10ULL>(
        bitmap, words, origin.low, origin.high, buffers.window_steps, buffers.gap_min,
        buffers.results + uint64_t(index) * buffers.result_capacity, buffers.result_capacity,
        buffers.stats + uint64_t(index) * 2, classes, batch_quotient,
        uint64_t(gridDim.x) * blockDim.x, uint64_t(blockIdx.x) * blockDim.x + threadIdx.x);
}
__global__ __maxnreg__(40) void pgn_graph_walk67_80(const PgnWalkDescriptor *descriptors,
                                                    const PgnWalkGraphState *state,
                                                    PgnWalkGraphBuffers buffers) {
    const uint32_t index = state->cursor;
    if (index >= state->count)
        return;
    const PgnWalkDescriptor descriptor = descriptors[index];
    const auto origin = pgn_class30_origin(descriptor);
    __shared__ uint32_t classes[8];
    __shared__ uint64_t batch_quotient;
    const uint64_t words = uint64_t(descriptor.bitmap_blocks) * ((1ULL << 28) / 64);
    if (threadIdx.x < 8)
        classes[threadIdx.x] = c30_cls[threadIdx.x];
#ifdef PGN_EULER96_BATCH_Q
    if (threadIdx.x == 0)
        batch_quotient = pgn_euler96::batchQuotient(origin.low, origin.high, words);
#else
    if (threadIdx.x == 0)
        batch_quotient = 0;
#endif
    __syncthreads();
    const auto *bitmap = buffers.bitmaps + uint64_t(index % PgnBitmapSlots) *
                                               buffers.blocks_per_slot * ((1ULL << 28) / 64);
    // Same ownership, Euler arithmetic and collective population as the paid
    // fixed-high-10 walk. This adapter deliberately rejects other high words.
    w_owned_slice<3, UINT64_MAX>(
        bitmap, words, origin.low, origin.high, buffers.window_steps, buffers.gap_min,
        buffers.results + uint64_t(index) * buffers.result_capacity, buffers.result_capacity,
        buffers.stats + uint64_t(index) * 2, classes, batch_quotient,
        uint64_t(gridDim.x) * blockDim.x, uint64_t(blockIdx.x) * blockDim.x + threadIdx.x);
}

struct PgnWalkMailbox {
    w_gaprec_t *results;
    unsigned long long *stats;
    volatile unsigned *ready, *stop, *done;
};
#ifdef PGN_VERIFY_GAPS
__global__ void pgn_graph_verify(const PgnWalkDescriptor *descriptors,
                                 const PgnWalkGraphState *state, PgnWalkGraphBuffers buffers) {
    const unsigned index = state->cursor;
    if (index >= state->count)
        return;
    const auto origin = pgn_class30_origin(descriptors[index]);
    const auto *source = buffers.results + uint64_t(index) * buffers.result_capacity;
    const unsigned count = source[0].gap;
    if (count >= buffers.result_capacity)
        return;
    for (unsigned row = 1 + blockIdx.x * blockDim.x + threadIdx.x; row <= count;
         row += gridDim.x * blockDim.x) {
        const auto gap = source[row];
        bool valid = gap.gap > 0 && gap.slot <= UINT64_MAX - gap.gap;
        if (valid)
            valid = pgn_mr96::screen13(gap.slot, origin.high) == 1 &&
                    pgn_mr96::screen13(gap.slot + gap.gap, origin.high) == 1;
        // Every inner integer has a real compositeness witness. Basic divisors
        // reject most; a failed exact Euler/Jacobi congruence rejects the rest.
        for (unsigned delta = 1; valid && delta < gap.gap; ++delta) {
            const uint64_t n = gap.slot + delta;
            if (!(n & 1) || (n % 3 + origin.high % 3) % 3 == 0 ||
                (n % 5 + origin.high % 5) % 5 == 0)
                continue;
            if (pgn_euler96::test(n, origin.high) && pgn_mr96::screen13(n, origin.high) != 0)
                valid = false;
        }
        buffers.proofs[uint64_t(index) * buffers.result_capacity + row] = valid ? 1u : 0u;
    }
}
#endif
// Each lane owns its cursor, bitmap parity, conditional handle and done word.
// It never waits for the other lane. ready[] remains descriptor-indexed; only
// the host's unchanged ordered-prefix consumer may credit an output.
__global__ void pgn_graph_advance(PgnWalkGraphState *state, unsigned *visits,
                                  PgnWalkGraphBuffers buffers, PgnWalkMailbox mailbox,
                                  cudaGraphConditionalHandle handle) {
    const unsigned finished = state->cursor;
    const auto *source = buffers.results + uint64_t(finished) * buffers.result_capacity;
    const unsigned reported = source[0].gap;
    if (reported >= buffers.result_capacity) {
        __threadfence_system();
        *mailbox.done = 2u;
        cudaGraphSetConditional(handle, 0);
        return;
    }
#ifdef PGN_VERIFY_GAPS
    for (unsigned row = 1; row <= reported; ++row)
        if (buffers.proofs[uint64_t(finished) * buffers.result_capacity + row] != 1u) {
            __threadfence_system();
            *mailbox.done = 3u;
            cudaGraphSetConditional(handle, 0);
            return;
        }
#endif
    auto *target = mailbox.results + uint64_t(finished) * buffers.result_capacity;
    for (unsigned row = 0; row <= reported; ++row)
        target[row] = source[row];
    for (unsigned stat = 0; stat < 2; ++stat)
        mailbox.stats[2 * finished + stat] = buffers.stats[2 * finished + stat];
    ++visits[finished];
    __threadfence_system();
    mailbox.ready[finished] = 1u;
    state->cursor += PgnDescriptorLanes;
    ++state->completed;
    const bool more = state->cursor < state->count && !*mailbox.stop;
    if (!more) {
        __threadfence_system();
        *mailbox.done = 1u;
    }
    cudaGraphSetConditional(handle, more ? 1 : 0);
}
#endif

__global__ __maxnreg__(40) void pgn_graph_walk67_h5(const PgnWalkDescriptor *descriptors,
                                                    const PgnWalkGraphState *state,
                                                    PgnWalkGraphBuffers buffers) {
    const uint32_t index = state->cursor;
    if (index >= state->count)
        return;
    const PgnWalkDescriptor descriptor = descriptors[index];
    const auto origin = pgn_class30_origin(descriptor);
    __shared__ uint32_t classes[8];
    __shared__ uint64_t batch_quotient;
    const uint64_t words = uint64_t(descriptor.bitmap_blocks) * ((1ULL << 28) / 64);
    if (threadIdx.x < 8)
        classes[threadIdx.x] = c30_cls[threadIdx.x];
#ifdef PGN_EULER96_BATCH_Q
    if (threadIdx.x == 0)
        batch_quotient = pgn_euler96::batchQuotient(origin.low, origin.high, words);
#else
    if (threadIdx.x == 0)
        batch_quotient = 0;
#endif
    __syncthreads();
    const auto *bitmap = buffers.bitmaps + uint64_t(index % PgnBitmapSlots) *
                                               buffers.blocks_per_slot * ((1ULL << 28) / 64);
    // Same ownership, Euler arithmetic and collective population as the paid
    // fixed-high-10 walk. This adapter deliberately rejects other high words.
    w_owned_slice<67, 5ULL>(
        bitmap, words, origin.low, origin.high, buffers.window_steps, buffers.gap_min,
        buffers.results + uint64_t(index) * buffers.result_capacity, buffers.result_capacity,
        buffers.stats + uint64_t(index) * 2, classes, batch_quotient,
        uint64_t(gridDim.x) * blockDim.x, uint64_t(blockIdx.x) * blockDim.x + threadIdx.x);
}

__global__ void pgn_graph_verify68_h10(const PgnWalkDescriptor *descriptors,
                                       const PgnWalkGraphState *state,
                                       PgnWalkGraphBuffers buffers) {
    const unsigned index = state->cursor;
    if (index >= state->count)
        return;
    const auto origin = pgn_class30_origin(descriptors[index]);
    if (origin.high != 10ULL)
        return; // private H10 only, unwritten proofs fail closed
    const auto *source = buffers.results + uint64_t(index) * buffers.result_capacity;
    const unsigned count = source[0].gap;
    if (count >= buffers.result_capacity)
        return;
    for (unsigned row = 1 + blockIdx.x * blockDim.x + threadIdx.x; row <= count;
         row += gridDim.x * blockDim.x) {
        const auto gap = source[row];
        bool valid = gap.gap > 0 && gap.slot <= UINT64_MAX - gap.gap;
        if (valid)
            valid = pgn_mr96::screen13(gap.slot, origin.high) == 1 &&
                    pgn_mr96::screen13(gap.slot + gap.gap, origin.high) == 1;
        // Every inner integer has a real compositeness witness. Basic divisors
        // reject most; a failed exact Euler/Jacobi congruence rejects the rest.
        // The walk's radix16 predicate uses a separate fresh state for each gap.
        // Full2^36 bucket tagging admits every halo/carry point; failed builder uses
        // exactly the old Barrett70 fallback. Endpoints/MR12/row order are unchanged.
        cached_euler68::State interiorState{};
        for (unsigned delta = 1; valid && delta < gap.gap; ++delta) {
            const uint64_t n = gap.slot + delta;
            if (!(n & 1) || (n % 3 + origin.high % 3) % 3 == 0 ||
                (n % 5 + origin.high % 5) % 5 == 0)
                continue;
            if (w_live_prime<3, 10ULL>(n, origin.high, 0ULL, interiorState) &&
                pgn_mr96::screen13(n, origin.high) != 0)
                valid = false;
        }
        buffers.proofs[uint64_t(index) * buffers.result_capacity + row] = valid ? 1u : 0u;
    }
}
__global__ void pgn_graph_verify67_h5(const PgnWalkDescriptor *descriptors,
                                      const PgnWalkGraphState *state, PgnWalkGraphBuffers buffers) {
    const unsigned index = state->cursor;
    if (index >= state->count)
        return;
    const auto origin = pgn_class30_origin(descriptors[index]);
    if (origin.high != 5ULL)
        return; // private H10 only, unwritten proofs fail closed
    const auto *source = buffers.results + uint64_t(index) * buffers.result_capacity;
    const unsigned count = source[0].gap;
    if (count >= buffers.result_capacity)
        return;
    for (unsigned row = 1 + blockIdx.x * blockDim.x + threadIdx.x; row <= count;
         row += gridDim.x * blockDim.x) {
        const auto gap = source[row];
        bool valid = gap.gap > 0 && gap.slot <= UINT64_MAX - gap.gap;
        if (valid)
            valid = pgn_mr96::screen13(gap.slot, origin.high) == 1 &&
                    pgn_mr96::screen13(gap.slot + gap.gap, origin.high) == 1;
        // Every inner integer has a real compositeness witness. Basic divisors
        // reject most; a failed exact Euler/Jacobi congruence rejects the rest.
        // The walk's radix16 predicate uses a separate fresh state for each gap.
        // Full2^36 bucket tagging admits every halo/carry point; failed builder uses
        // exactly the old Barrett70 fallback. Endpoints/MR12/row order are unchanged.
        cached_euler67::State interiorState{};
        for (unsigned delta = 1; valid && delta < gap.gap; ++delta) {
            const uint64_t n = gap.slot + delta;
            if (!(n & 1) || (n % 3 + origin.high % 3) % 3 == 0 ||
                (n % 5 + origin.high % 5) % 5 == 0)
                continue;
            if (w_live_prime<67, 5ULL>(n, origin.high, 0ULL, interiorState) &&
                pgn_mr96::screen13(n, origin.high) != 0)
                valid = false;
        }
        buffers.proofs[uint64_t(index) * buffers.result_capacity + row] = valid ? 1u : 0u;
    }
}

// Each specialization keeps its own modular arithmetic and state type. These
// shared bodies only express identical range ownership, publication and proof
// rules; kernel geometry and register ceilings are unchanged.
template <int Bits, uint64_t High>
__device__ __forceinline__ void walkSpecialized(const PgnWalkDescriptor *descriptors,
                                                const PgnWalkGraphState *state,
                                                PgnWalkGraphBuffers buffers) {
    const uint32_t index = state->cursor;
    if (index >= state->count)
        return;
    const auto descriptor = descriptors[index];
    const auto origin = pgn_class30_origin(descriptor);
    __shared__ uint32_t classes[8];
    __shared__ uint64_t batchQuotient;
    const uint64_t words = uint64_t(descriptor.bitmap_blocks) * ((1ULL << 28) / 64);
    if (threadIdx.x < 8)
        classes[threadIdx.x] = c30_cls[threadIdx.x];
#ifdef PGN_EULER96_BATCH_Q
    if (threadIdx.x == 0)
        batchQuotient = pgn_euler96::batchQuotient(origin.low, origin.high, words);
#else
    if (threadIdx.x == 0)
        batchQuotient = 0;
#endif
    __syncthreads();
    const auto *bitmap = buffers.bitmaps + uint64_t(index % PgnBitmapSlots) *
                                               buffers.blocks_per_slot * ((1ULL << 28) / 64);
    w_owned_slice<Bits, High>(
        bitmap, words, origin.low, origin.high, buffers.window_steps, buffers.gap_min,
        buffers.results + uint64_t(index) * buffers.result_capacity, buffers.result_capacity,
        buffers.stats + uint64_t(index) * 2, classes, batchQuotient,
        uint64_t(gridDim.x) * blockDim.x, uint64_t(blockIdx.x) * blockDim.x + threadIdx.x);
}

template <int Bits, uint64_t High>
__device__ __forceinline__ void verifySpecialized(const PgnWalkDescriptor *descriptors,
                                                  const PgnWalkGraphState *state,
                                                  PgnWalkGraphBuffers buffers) {
    const unsigned index = state->cursor;
    if (index >= state->count)
        return;
    const auto origin = pgn_class30_origin(descriptors[index]);
    if (origin.high != High)
        return; // No publication on a mismatched specialization.
    const auto *source = buffers.results + uint64_t(index) * buffers.result_capacity;
    const unsigned count = source[0].gap;
    if (count >= buffers.result_capacity)
        return;
    for (unsigned row = 1 + blockIdx.x * blockDim.x + threadIdx.x; row <= count;
         row += gridDim.x * blockDim.x) {
        const auto gap = source[row];
        bool valid = gap.gap > 0 && gap.slot <= UINT64_MAX - gap.gap;
        if (valid)
            valid = pgn_mr96::screen13(gap.slot, origin.high) == 1 &&
                    pgn_mr96::screen13(gap.slot + gap.gap, origin.high) == 1;
        typename pgn_release_live_state<Bits>::type interiorState{};
        for (unsigned delta = 1; valid && delta < gap.gap; ++delta) {
            const uint64_t n = gap.slot + delta;
            if (!(n & 1) || (n % 3 + origin.high % 3) % 3 == 0 ||
                (n % 5 + origin.high % 5) % 5 == 0)
                continue;
            // A failed Euler or MR congruence is an exact compositeness witness.
            // Positive endpoints above the deterministic MR13 bound are proved by the
            // host before the complete descriptor is emitted or checkpointed.
            if (w_live_prime<Bits, High>(n, origin.high, 0ULL, interiorState) &&
                pgn_mr96::screen13(n, origin.high) != 0)
                valid = false;
        }
        buffers.proofs[uint64_t(index) * buffers.result_capacity + row] = valid ? 1u : 0u;
    }
}

#define SCOUT_BASE_ENGINE(BITS, HIGH, GAP, STATE_BYTES)
#define SCOUT_SPECIALIZED_ENGINE(BITS, HIGH, GAP, STATE_BYTES)                                     \
    __global__ __maxnreg__(40) void pgn_graph_walk##BITS##_retained_h##HIGH(                       \
        const PgnWalkDescriptor *d, const PgnWalkGraphState *s, PgnWalkGraphBuffers b) {           \
        walkSpecialized<BITS, HIGH##ULL>(d, s, b);                                                 \
    }                                                                                              \
    __global__ void pgn_graph_verify##BITS##_retained_h##HIGH(                                     \
        const PgnWalkDescriptor *d, const PgnWalkGraphState *s, PgnWalkGraphBuffers b) {           \
        verifySpecialized<BITS, HIGH##ULL>(d, s, b);                                               \
    }
#include "specialized_engines.def"
#undef SCOUT_SPECIALIZED_ENGINE
#undef SCOUT_BASE_ENGINE
