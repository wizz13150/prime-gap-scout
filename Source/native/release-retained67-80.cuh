#pragma once
#include <stdint.h>
#include <math.h>
#if defined(__CUDACC__)
#define PGN_RETAINED_HD __host__ __device__ __forceinline__
#else
#define PGN_RETAINED_HD inline
#endif
// Per-family namespaces preserve original header bodies and isolate identical filenames.
namespace pgn_release_backend69 {
namespace impl {
#include "release69/fast69-specialized.cuh"
}
using State=impl::pgn_fast_domains_stateful::State;
static_assert(sizeof(State)==32,"Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::pgn_fast69::test(low,21u,state);}
}
namespace pgn_release_backend70 {
namespace impl {
#include "release70/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==8,"Exact retained point State8");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend71 {
namespace impl {
#include "release71/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==8,"Exact retained point State8");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend72 {
namespace impl {
#include "release72/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==32,"Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend73 {
namespace impl {
#include "release73/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==32,"Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend74 {
namespace impl {
#include "release74/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==32,"Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend75 {
namespace impl {
#include "release75/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==32,"Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend76 {
namespace impl {
#include "release76/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==32,"Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend77 {
namespace impl {
#include "release77/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==32,"Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend78 {
namespace impl {
#include "release78/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==8,"Exact retained point State8");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend79 {
namespace impl {
#include "release79/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==8,"Exact retained point State8");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
namespace pgn_release_backend80 {
namespace impl {
#include "release80/whole68-port-math.cuh"
}
using State=impl::whole68_port::State;
static_assert(sizeof(State)==32,"Exact retained point State32");
PGN_RETAINED_HD bool test(uint64_t low,State&state){return impl::whole68_port::test(low,state);}
}
#undef PGN_RETAINED_HD
