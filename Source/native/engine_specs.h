#pragma once
#include <cstdint>

namespace scout {
struct EngineSpec {
    unsigned bits;
    uint64_t highWord;
    unsigned automaticGap;
    unsigned stateBytes;
    const char *name;
};
#define SCOUT_BASE_ENGINE(BITS, HIGH, GAP, STATE_BYTES)                                            \
    {BITS, HIGH##ULL, GAP, STATE_BYTES, "euler" #BITS},
#define SCOUT_SPECIALIZED_ENGINE SCOUT_BASE_ENGINE
inline constexpr EngineSpec Engines[] = {
#include "specialized_engines.def"
};
#undef SCOUT_SPECIALIZED_ENGINE
#undef SCOUT_BASE_ENGINE
inline const EngineSpec *engineForHigh(uint64_t high) {
    for (const auto &engine : Engines)
        if (engine.highWord == high)
            return &engine;
    return nullptr;
}
} // namespace scout
