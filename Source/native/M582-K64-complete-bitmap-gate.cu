// C26 SOURCE ONLY: complete bitmap inter-variant CUDA gate.
// NO throughput, primality, allG or Native qualification is claimed.
// The two mark bodies below are copied from their pinned production sources.
// Parent: only pgn_graph_mark -> c26_parent_mark.
// Candidate: only pgn_graph_mark -> c26_plane_mark and its buffer type renamed.
// This translation unit intentionally does not include either graph scheduler.
#include <cuda_runtime.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <stdexcept>
#include <string>
#include <vector>
#include "C26-host-domain.h"

#ifndef PGN_FUSED_SIEVE
#define PGN_FUSED_SIEVE 1
#endif
#ifndef PGN_PRESIEVE_GROUPS
#define PGN_PRESIEVE_GROUPS 1
#endif
static_assert(PGN_PRESIEVE_GROUPS==1, "Use the retained Tiny1001/periodic7429/Low7 profile");
#ifdef PGN_VERIFY_GAPS
#error This bitmap-only gate must not compile graph proof or Euler consumers.
#endif
#ifndef PGN_MARK_FULL_FAST
#define PGN_MARK_FULL_FAST 1
#endif
#ifndef PGN_MARK_BANK_ROTATE
#define PGN_MARK_BANK_ROTATE 1
#endif
#include "stateful-u160-live.cuh"
#include "p0_walk_kern.cuh"
#include "M582-counterfree-cycle8-marker.cuh"

#ifndef PGN_DESCRIPTOR_LANES
#define PGN_DESCRIPTOR_LANES 2
#endif
constexpr unsigned PgnDescriptorLanes=PGN_DESCRIPTOR_LANES;
constexpr unsigned PgnBitmapSlots=2*PgnDescriptorLanes;
static_assert(PgnDescriptorLanes==2||PgnDescriptorLanes==4||PgnDescriptorLanes==8||PgnDescriptorLanes==16||PgnDescriptorLanes==32||PgnDescriptorLanes==64,"Finite lane candidates only");
struct PgnWalkDescriptor {
    uint64_t low, high;
    uint32_t bitmap_blocks, owned_blocks;
};
struct PgnClass30Origin {uint64_t low, high;};
__device__ __forceinline__ PgnClass30Origin pgn_class30_origin(PgnWalkDescriptor descriptor) {
    const uint64_t remainder=(descriptor.low%30+(descriptor.high%30)*16)%30;
    return {descriptor.low-remainder,descriptor.high-(descriptor.low<remainder?1:0)};
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

struct PgnPlaneGraphBuffers {
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
__global__ __maxnreg__(48) void c26_parent_mark(const PgnWalkDescriptor *descriptors,
 const PgnWalkGraphState *state, PgnWalkGraphBuffers buffers, uint32_t ahead) {
    const uint32_t index=state->cursor+ahead;
    // The predicate is uniform for the entire CTA, before any shared barrier.
    if(index>=state->count)return;
    const PgnWalkDescriptor descriptor=descriptors[index];

    // Keep the descriptor cursor separate from the sieve's class-30 base.
    // 2^64 mod30=16; rounding a sieve must not redefine reporting ownership.
    const auto origin=pgn_class30_origin(descriptor);
    constexpr uint64_t words=(1ULL<<28)/64;
    auto *bitmap=buffers.bitmaps+uint64_t(index%PgnBitmapSlots)*buffers.blocks_per_slot*words;
    // Repartition eachbitmap into16 contiguous32-tile cohorts; stride1 root reuse.
    // A bounded physical grid finishes dispatch quickly, leaving capacity for
    // already-ready walk/control kernels. Every CTA loop is uniform and finite.
    for(unsigned job=blockIdx.x;job<16u*descriptor.bitmap_blocks;job+=gridDim.x){
        const unsigned cohort=job%16u,logicalY=job/16u;
        const uint64_t displacement=uint64_t(cohort)*32u*((1ULL<<19)/8)*30u;
        const uint64_t low=origin.low+displacement;
        const uint64_t high=origin.high+uint64_t(low<origin.low);
        // Contiguous32-tile ownership; all16cohorts cover exactly512tiles.
        class30_sieve_body<true,true,true,true>(buffers.primes,buffers.invp,buffers.r64,
            buffers.item_pidx,buffers.item_k0,buffers.item_count,
            low,high,1ULL<<19,32,bitmap+uint64_t(cohort)*32u*8192u,8192,
            buffers.wheel_primes,1,buffers.root_steps,0,logicalY,1);
        __syncthreads();
    }
}

__global__ __maxnreg__(48) void c26_plane_mark(const PgnWalkDescriptor *descriptors,
 const PgnWalkGraphState *state, PgnPlaneGraphBuffers buffers, uint32_t ahead) {
    const uint32_t index=state->cursor+ahead;
    // The predicate is uniform for the entire CTA, before any shared barrier.
    if(index>=state->count)return;
    const PgnWalkDescriptor descriptor=descriptors[index];

    // Keep the descriptor cursor separate from the sieve's class-30 base.
    // 2^64 mod30=16; rounding a sieve must not redefine reporting ownership.
    const auto origin=pgn_class30_origin(descriptor);
    constexpr uint64_t words=(1ULL<<28)/64;
    auto *bitmap=buffers.bitmaps+uint64_t(index%PgnBitmapSlots)*buffers.blocks_per_slot*words;
    // Repartition eachbitmap into16 contiguous32-tile cohorts; stride1 root reuse.
    // A bounded physical grid finishes dispatch quickly, leaving capacity for
    // already-ready walk/control kernels. Every CTA loop is uniform and finite.
    for(unsigned job=blockIdx.x;job<16u*descriptor.bitmap_blocks;job+=gridDim.x){
        const unsigned cohort=job%16u,logicalY=job/16u;
        const uint64_t displacement=uint64_t(cohort)*32u*((1ULL<<19)/8)*30u;
        const uint64_t low=origin.low+displacement;
        const uint64_t high=origin.high+uint64_t(low<origin.low);
        // Contiguous32-tile ownership; all16cohorts cover exactly512tiles.
        m582_counterfree::body<true,true,true,true>(buffers.primes,buffers.invp,buffers.r64,
            buffers.item_pidx,buffers.item_k0,buffers.item_count,
            low,high,1ULL<<19,32,bitmap+uint64_t(cohort)*32u*8192u,8192,
            buffers.wheel_primes,1,buffers.root_steps,0,logicalY,1);
        __syncthreads();
    }
}

namespace c26 {
constexpr unsigned Depth=80000, PrimeCount=7834, EventPrimeCount=4200;
constexpr uint64_t BlockWords=(1ULL<<28)/64, LogicalBlocks=65;
constexpr uint64_t TotalWords=LogicalBlocks*BlockWords;
constexpr uint64_t GuardWords=32, Guard=0xd3d3d3d3d3d3d3d3ULL;
constexpr unsigned ParentThreads=512, PlaneThreads=512;
constexpr unsigned ParentDynamic=65536, PlaneDynamic=65536;
static_assert(BlockWords==4194304 && TotalWords==272629760, "Full K64 plus one bitmap halo block");
constexpr unsigned NativeOwners=164u*512u;
static_assert(NativeOwners==83968, "Exact native owner count, not fixture slots");
static_assert(PrimeCount==7834 && Depth==80000, "M582 exact retained bank");
static bool runtimeTainted=false;
struct Allocations {
    std::vector<void*> values;
    ~Allocations(){if(runtimeTainted)return;for(auto p:values)if(p){if(cudaFree(p)!=cudaSuccess){runtimeTainted=true;break;}}}
    template<class T> cudaError_t allocate(T*& p,size_t count){
        cudaError_t e=cudaMalloc(reinterpret_cast<void**>(&p),count*sizeof(T));
        if(e==cudaSuccess)values.push_back(p);return e;
    }
};
#define C26_CU(call) do { const cudaError_t err=(call); if(err!=cudaSuccess){ runtimeTainted=true; \
 std::fprintf(stderr,"C26 CUDA error: %s at line %d (%s)\n", \
 cudaGetErrorString(err),__LINE__,#call);return 3;} } while(0)
template<class T> cudaError_t upload(Allocations& a,T*& p,const std::vector<T>& h){
    cudaError_t e=a.allocate(p,h.size());if(e!=cudaSuccess)return e;
    return cudaMemcpy(p,h.data(),h.size()*sizeof(T),cudaMemcpyHostToDevice);
}
std::string uuidText(const cudaUUID_t& id){
    static const char hex[]="0123456789abcdef";std::string s="GPU-";
    for(unsigned i=0;i<16;++i){
        if(i==4||i==6||i==8||i==10)s+='-';
        const unsigned b=static_cast<unsigned char>(id.bytes[i]);
        s+=hex[b>>4];s+=hex[b&15];
    }return s;
}
std::string lower(std::string s){
    for(char& c:s)if(c>='A'&&c<='Z')c=char(c-'A'+'a');return s;
}
using OriginCase=c26_host_domain::OriginCase;
struct Difference {unsigned long long count=0,first=~0ULL;};
static_assert(sizeof(Difference)==16,"Only16 comparator bytes cross to the host");
// Every data word i belongs to exactly one thread: i = tid + k*(grid*block).
// No hash, sampling, early exit, or bitmap transfer to the host is used.
// Launch contract:256 full threads/CTA,8 full warps; all lanes reach shuffles
// after their finite grid-stride loop, and every CTA thread reaches the barrier.
__global__ void compareExactWords(const uint64_t* parent,const uint64_t* plane,
    uint64_t words,Difference* result){
    constexpr unsigned FullMask=0xffffffffu;
    __shared__ unsigned long long warpCounts[8],warpFirst[8];
    unsigned long long localCount=0,localFirst=~0ULL;
    const uint64_t stride=uint64_t(gridDim.x)*blockDim.x;
    for(uint64_t at=uint64_t(blockIdx.x)*blockDim.x+threadIdx.x;at<words;at+=stride){
        if(parent[at]!=plane[at]){++localCount;if(at<localFirst)localFirst=at;}
    }
    // All32 lanes participate after the loop, including lanes with zero words.
    for(unsigned step=16;step;step>>=1){
        localCount+=__shfl_down_sync(FullMask,localCount,step);
        const unsigned long long other=__shfl_down_sync(FullMask,localFirst,step);
        if(other<localFirst)localFirst=other;
    }
    const unsigned lane=threadIdx.x&31u,warp=threadIdx.x>>5;
    if(!lane){warpCounts[warp]=localCount;warpFirst[warp]=localFirst;}
    __syncthreads();
    // The complete first warp reduces the8 warp records. Other warps are done.
    if(!warp){
        localCount=lane<8?warpCounts[lane]:0;
        localFirst=lane<8?warpFirst[lane]:~0ULL;
        for(unsigned step=16;step;step>>=1){
            localCount+=__shfl_down_sync(FullMask,localCount,step);
            const unsigned long long other=__shfl_down_sync(FullMask,localFirst,step);
            if(other<localFirst)localFirst=other;
        }
        if(!lane&&localCount){
            // At most ONE add and ONE min per CTA, even if every word differs.
            atomicAdd(&result->count,localCount);atomicMin(&result->first,localFirst);
        }
    }
}
cudaError_t compareAll(const uint64_t* parent,const uint64_t* plane,
    uint64_t words,Difference& difference){
    Difference* deviceResult=nullptr;difference={};
    cudaError_t error=cudaMalloc(&deviceResult,sizeof(Difference));
    if(error!=cudaSuccess)return error;
    error=cudaMemcpy(deviceResult,&difference,sizeof(Difference),cudaMemcpyHostToDevice);
    if(error==cudaSuccess){
        compareExactWords<<<256,256>>>(parent,plane,words,deviceResult);
        error=cudaGetLastError();
    }
    if(error==cudaSuccess)
        error=cudaMemcpy(&difference,deviceResult,sizeof(Difference),cudaMemcpyDeviceToHost);
    if(error!=cudaSuccess){runtimeTainted=true;return error;}
    const cudaError_t release=cudaFree(deviceResult);
    if(release!=cudaSuccess)runtimeTainted=true;
    return release;
}
cudaError_t checkGuards(const uint64_t* allocation,uint64_t words,bool& good){
    uint64_t x[GuardWords*2];good=true;
    cudaError_t e=cudaMemcpy(x,allocation,GuardWords*8,cudaMemcpyDeviceToHost);
    if(e!=cudaSuccess)return e;
    e=cudaMemcpy(x+GuardWords,allocation+GuardWords+words,
                 GuardWords*8,cudaMemcpyDeviceToHost);
    if(e!=cudaSuccess)return e;
    for(auto v:x)if(v!=Guard)good=false;return cudaSuccess;
}
__global__ void flipOne(uint64_t* words,uint64_t at,uint64_t bit){
    if(!blockIdx.x&&!threadIdx.x)words[at]^=bit;
}
int run(int device,const std::string& expectedUuid,unsigned bitmapBlocks){
    if(bitmapBlocks!=1&&bitmapBlocks!=2&&bitmapBlocks!=65)return 2;
    const uint64_t totalWords=uint64_t(bitmapBlocks)*BlockWords;
    // HOST admission of ALL cases and their entire extent BEFORE any CUDA API.
    if(!c26_host_domain::validateAll(bitmapBlocks)){
        std::fputs("C26 HOST domain admission refused before CUDA\n",stderr);return 2;
    }
    // The owner must acquire the resource lease BEFORE invoking this binary.
    // UUID + sm86 admission protects against an accidental different GPU.
    int count=0;C26_CU(cudaGetDeviceCount(&count));
    if(device<0||device>=count){std::fputs("C26 invalid explicit device\n",stderr);return 2;}
    cudaDeviceProp props{};C26_CU(cudaGetDeviceProperties(&props,device));
    const std::string actual=uuidText(props.uuid);
    if(props.major!=8||props.minor!=6||lower(actual)!=lower(expectedUuid)){
        std::fprintf(stderr,"C26 admission refused: actual %s sm_%d%d\n",
                     actual.c_str(),props.major,props.minor);return 2;
    }
    C26_CU(cudaSetDevice(device));
    std::printf("C26 ADMITTED %s sm_86 bitmap_intervariant_only=1\n",actual.c_str());
    Allocations allocations;
    std::vector<unsigned char> composite(Depth+1);
    for(unsigned p=2;p*p<=Depth;++p)if(!composite[p])
        for(unsigned j=p*p;j<=Depth;j+=p)composite[j]=1;
    std::vector<uint64_t> primes,inverses,r64;
    std::vector<uint32_t> itemPidx,itemK0,rootSteps;
    uint32_t wheel[3]={};
    for(unsigned p=7;p<=Depth;p+=2)if(!composite[p]){
        const unsigned pi=unsigned(primes.size());primes.push_back(p);
        inverses.push_back(UINT64_MAX/p);r64.push_back((UINT64_MAX%p+1)%p);
        if(p==7)wheel[0]=pi;if(p==11)wheel[1]=pi;if(p==13)wheel[2]=pi;
        if(p>PgnPreMax)
            for(unsigned chunk=0;chunk<((1u<<19)/p+2+255)/256;++chunk){
                itemPidx.push_back(pi);itemK0.push_back(chunk);
            }
        rootSteps.push_back(uint32_t((((1ULL<<19)/8)*30)%p));
    }
    if(primes.size()!=PrimeCount || primes[4199]!=39989 ||
       primes[560]!=4093 || primes[561]!=4099 ||
       primes[4285]!=40961 || primes.back()!=79999){
        std::fputs("C26 wrong ascending 7834-prime bank\n",stderr);return 2;
    }
    // CRITICAL: the native Event210 helper is licensed only through p<=40000.
    // Do NOT feed all 7834 entries to upload(). The remaining AP bank stays full.
    const std::vector<uint64_t> prefixPrimes(primes.begin(),primes.begin()+EventPrimeCount);
    const auto eventHost=pgn_event210::makePrefix(prefixPrimes);
    if(eventHost.size()!=EventPrimeCount*96u)return 2;
    uint32_t* eventDevice=nullptr;C26_CU(upload(allocations,eventDevice,eventHost));
    C26_CU(cudaMemcpyToSymbol(pgn_event210::prefix,&eventDevice,sizeof(eventDevice)));
    // Retain the exact class30, Tiny1001, periodic7429 and Low7 implementations.
    // Tiny/Low7 are immutable device tables in the pinned parent headers.
    const uint32_t classes[8]={1,7,11,13,17,19,23,29};
    int8_t index[30];std::memset(index,-1,sizeof(index));
    uint32_t permutation[30]={},inverse30[30]={};
    for(unsigned j=0;j<8;++j)index[classes[j]]=int8_t(j);
    for(unsigned p=0;p<30;++p)if(index[p]>=0){
        for(unsigned j=0;j<8;++j)permutation[p]|=1u<<((p*classes[j])%30);
        for(unsigned x=1;x<30;++x)if(p*x%30==1)inverse30[p]=x;
    }
    C26_CU(cudaMemcpyToSymbol(c30_clsidx,index,sizeof(index)));
    C26_CU(cudaMemcpyToSymbol(c30_perm,permutation,sizeof(permutation)));
    C26_CU(cudaMemcpyToSymbol(c30_pinv,inverse30,sizeof(inverse30)));
    const uint64_t* presieve[5]={};
    for(unsigned g=0;g<PGN_PRESIEVE_GROUPS;++g){
        const auto h=pgnMakePreTable(g);uint64_t* p=nullptr;
        C26_CU(upload(allocations,p,h));presieve[g]=p;
    }
    C26_CU(cudaMemcpyToSymbol(pgn_pre_tables,presieve,sizeof(presieve)));
    uint64_t *dp=nullptr,*di=nullptr,*dr=nullptr;
    uint32_t *dItems=nullptr,*dChunks=nullptr,*dRoots=nullptr,*dWheel=nullptr;
    C26_CU(upload(allocations,dp,primes));C26_CU(upload(allocations,di,inverses));
    C26_CU(upload(allocations,dr,r64));C26_CU(upload(allocations,dItems,itemPidx));
    C26_CU(upload(allocations,dChunks,itemK0));C26_CU(upload(allocations,dRoots,rootSteps));
    C26_CU(allocations.allocate(dWheel,size_t(3)));
    C26_CU(cudaMemcpy(dWheel,wheel,sizeof(wheel),cudaMemcpyHostToDevice));
    uint64_t *parentAllocation=nullptr,*planeAllocation=nullptr;
    C26_CU(allocations.allocate(parentAllocation,size_t(totalWords+2*GuardWords)));
    C26_CU(allocations.allocate(planeAllocation,size_t(totalWords+2*GuardWords)));
    auto* parentWords=parentAllocation+GuardWords;
    auto* planeWords=planeAllocation+GuardWords;
    PgnWalkDescriptor* descriptor=nullptr;PgnWalkGraphState* state=nullptr;
    C26_CU(allocations.allocate(descriptor,size_t(5)));C26_CU(allocations.allocate(state,size_t(1)));
    const PgnWalkGraphState initial{0,5,0};
    C26_CU(cudaMemcpy(state,&initial,sizeof(initial),cudaMemcpyHostToDevice));
    PgnWalkGraphBuffers parent{};
    parent.primes=dp;parent.invp=di;parent.r64=dr;
    parent.item_pidx=dItems;parent.item_k0=dChunks;
    parent.item_count=unsigned(itemPidx.size());parent.wheel_primes=dWheel;
    parent.root_steps=dRoots;parent.blocks_per_slot=bitmapBlocks;
    parent.bitmaps=parentWords;
    PgnPlaneGraphBuffers plane{};
    plane.primes=dp;plane.invp=di;plane.r64=dr;
    plane.item_pidx=dItems;plane.item_k0=dChunks;
    plane.item_count=unsigned(itemPidx.size());plane.wheel_primes=dWheel;
    plane.root_steps=dRoots;plane.blocks_per_slot=bitmapBlocks;
    plane.bitmaps=planeWords;
    C26_CU(cudaFuncSetAttribute(c26_parent_mark,cudaFuncAttributeMaxDynamicSharedMemorySize,ParentDynamic));
    C26_CU(cudaFuncSetAttribute(c26_plane_mark,cudaFuncAttributeMaxDynamicSharedMemorySize,PlaneDynamic));
    // Both bitmaps are live. Prefix/tables remain live until both launches and
    // all complete comparisons have synchronized. There is NO graph replay.
    const auto& cases=c26_host_domain::Cases;
    const uint64_t poisonAt[]={totalWords/2+3,totalWords-1,0,bitmapBlocks>1?BlockWords:BlockWords-1};
    // Grid17 forces shared-state reinitialization across61/62 jobs per CTA.
    // Grid82 retains the original physical launch width and executes12/13 jobs per CTA.
    const unsigned grids[]={82,17,17,82};
    for(unsigned ci=0;ci<sizeof(cases)/sizeof(cases[0]);++ci){
        const auto& c=cases[ci];const unsigned grid=grids[ci];
        const unsigned rem=unsigned((c.low%30+(c.high%30)*16)%30);
        const uint64_t originLow=c.low-rem,originHigh=c.high-uint64_t(c.low<rem);
        // Index4 reuses native ring slot0: same modulo4 address, fresh epoch.
        const unsigned descriptorIndex=(ci&1u)?4u:0u;
        const PgnWalkDescriptor d{c.low,c.high,bitmapBlocks,bitmapBlocks==1?1u:bitmapBlocks-1u};
        C26_CU(cudaMemcpy(descriptor+descriptorIndex,&d,sizeof(d),cudaMemcpyHostToDevice));
        const PgnWalkGraphState generation{descriptorIndex,5,0};
        C26_CU(cudaMemcpy(state,&generation,sizeof(generation),cudaMemcpyHostToDevice));
        C26_CU(cudaMemset(parentAllocation,0xd3,size_t(totalWords+2*GuardWords)*8));
        C26_CU(cudaMemset(planeAllocation,0xd3,size_t(totalWords+2*GuardWords)*8));
        // Distinct fill bytes expose identical uninitialized/unwritten holes.
        C26_CU(cudaMemset(parentWords,0xa5,size_t(totalWords)*8));
        C26_CU(cudaMemset(planeWords,0x5a,size_t(totalWords)*8));
        // Hostile comparator control: EVERY initial data word differs.
        if(!ci){
            Difference allDifferent{};C26_CU(compareAll(parentWords,planeWords,totalWords,allDifferent));
            if(allDifferent.count!=totalWords||allDifferent.first!=0)return 10;
        }
        c26_parent_mark<<<grid,ParentThreads,ParentDynamic>>>(descriptor,state,parent,0);
        C26_CU(cudaGetLastError());C26_CU(cudaDeviceSynchronize());
        c26_plane_mark<<<grid,PlaneThreads,PlaneDynamic>>>(descriptor,state,plane,0);
        C26_CU(cudaGetLastError());C26_CU(cudaDeviceSynchronize());
        bool pg=false,cg=false;
        C26_CU(checkGuards(parentAllocation,totalWords,pg));C26_CU(checkGuards(planeAllocation,totalWords,cg));
        if(!pg||!cg){std::fprintf(stderr,"C26 output guard failed case %u\n",ci);return 4;}
        Difference d0{};C26_CU(compareAll(parentWords,planeWords,totalWords,d0));
        if(d0.count){
            std::fprintf(stderr,"C26 FULL_BITMAP_MISMATCH case %u words %llu first %llu\n",
              ci,(unsigned long long)d0.count,(unsigned long long)d0.first);
            return 5;
        }
        const uint64_t bit=1ULL<<((17u*ci+9u)&63u);
        flipOne<<<1,1>>>(planeWords,poisonAt[ci],bit);
        C26_CU(cudaGetLastError());C26_CU(cudaDeviceSynchronize());
        Difference poisoned{};C26_CU(compareAll(parentWords,planeWords,totalWords,poisoned));
        if(poisoned.count!=1 || poisoned.first!=poisonAt[ci]){
            std::fprintf(stderr,"C26 one-bit poison NOT detected exactly case %u\n",ci);return 6;
        }
        std::printf("C26 case=%s descriptor=%llu:%llu aligned=%llu:%llu logicalY=%u grid=%u "
          "exact_words=%llu guards=PASS poison_at=%llu poison=PASS\n",
          c.name,(unsigned long long)c.high,(unsigned long long)c.low,
          (unsigned long long)originHigh,(unsigned long long)originLow,bitmapBlocks,grid,
          (unsigned long long)totalWords,(unsigned long long)poisonAt[ci]);
    }
    // Uniform inactive-descriptor path must not touch either bitmap or guards.
    const PgnWalkGraphState inactive{5,5,0};
    C26_CU(cudaMemcpy(state,&inactive,sizeof(inactive),cudaMemcpyHostToDevice));
    c26_parent_mark<<<82,ParentThreads,ParentDynamic>>>(descriptor,state,parent,0);
    C26_CU(cudaGetLastError());
    c26_plane_mark<<<82,PlaneThreads,PlaneDynamic>>>(descriptor,state,plane,0);
    C26_CU(cudaGetLastError());
    C26_CU(cudaDeviceSynchronize());
    bool inactiveParent=false,inactivePlane=false;
    C26_CU(checkGuards(parentAllocation,totalWords,inactiveParent));
    C26_CU(checkGuards(planeAllocation,totalWords,inactivePlane));
    if(!inactiveParent||!inactivePlane)return 8;
    Difference afterInactive{};C26_CU(compareAll(parentWords,planeWords,totalWords,afterInactive));
    if(afterInactive.count!=1||afterInactive.first!=poisonAt[3])return 9;
    std::printf("C26 %s cases=4 primes=7834 depth=80000 "
      "EventPrefixPrimes=4200 scalar_cycle8=1 AP8_reconstruction=0 full_words_per_case=%llu "
      "bitmap_blocks=%u owned_blocks=%u bitmap_halo_blocks=%u owners=83968 "
      "ring_epochs=0,4 exact_GPU_comparator=1 host_bitmap_bytes=0 "
      "Native_perf=NOT_MEASURED primality=NOT_CLAIMED allG_Native=NOT_CLAIMED\n",
      bitmapBlocks==65?"COMPLETE_BITMAP_INTERVARIANT_PASS":"STAGED_BITMAP_INTERVARIANT_PASS",
      (unsigned long long)totalWords,bitmapBlocks,bitmapBlocks==1?1u:bitmapBlocks-1u,
      bitmapBlocks==1?0u:1u);
    return 0;
}
} // namespace c26
int main(int argc,char** argv){
    if((argc!=5&&argc!=7) || std::strcmp(argv[1],"--device") || std::strcmp(argv[3],"--uuid")){
        std::fputs("SOURCE-ONLY gate; OWNER must compile/admit/run. Usage: "
                   "C26-complete-bitmap-gate --device ORDINAL --uuid GPU-... [--bitmap-blocks 1|2|65]\n",stderr);
        return 2;
    }
    char* end=nullptr;const long device=std::strtol(argv[2],&end,10);
    if(!end || end==argv[2] || *end || device<0 || device>1024)return 2;
    unsigned blocks=65;
    if(argc==7){
        if(std::strcmp(argv[5],"--bitmap-blocks"))return 2;
        if(!std::strcmp(argv[6],"1"))blocks=1;
        else if(!std::strcmp(argv[6],"2"))blocks=2;
        else if(std::strcmp(argv[6],"65"))return 2;
    }
    try{return c26::run(int(device),argv[4],blocks);}
    catch(const std::exception& e){std::fprintf(stderr,"C26 exception: %s\n",e.what());return 7;}
}




