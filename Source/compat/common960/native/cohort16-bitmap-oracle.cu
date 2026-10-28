// Standalone mapping proof. The reference retains the qualified92-cohort
// partition; the candidate is the real16-cohort mark kernel, all words checked.
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <vector>
#include <fstream>
#include "pgn_conditional_walk.cuh"
#define CU(call) do{auto e=(call);if(e!=cudaSuccess){std::fprintf(stderr,"CUDA %s line%d\n",cudaGetErrorString(e),__LINE__);return 3;}}while(0)
__global__ void referenceMark92(uint64_t low,uint64_t high,PgnWalkGraphBuffers b){
 for(unsigned job=blockIdx.x;job<92u;job+=gridDim.x){
  class30_sieve_body<true,false>(b.primes,b.invp,b.r64,b.item_pidx,b.item_k0,b.item_count,
   low,high,1ULL<<19,512,b.bitmaps,8192,b.wheel_primes,1,b.root_steps,job,0,92);
  __syncthreads();
 }
}
int main(){
 constexpr unsigned Depth=40000;constexpr uint64_t Words=(1ULL<<28)/64;
 std::vector<unsigned char> composite(Depth+1);
 for(unsigned i=2;i*i<=Depth;++i)if(!composite[i])for(unsigned j=i*i;j<=Depth;j+=i)composite[j]=1;
 std::vector<uint64_t> primes,reciprocals,r64;
 std::vector<uint32_t> item_pidx,item_k0,roots1,roots92;uint32_t wheel_primes[3]{};
 for(unsigned p=7;p<=Depth;p+=2)if(!composite[p]){
  const unsigned index=unsigned(primes.size());primes.push_back(p);reciprocals.push_back(UINT64_MAX/p);r64.push_back((UINT64_MAX%p+1)%p);
  if(p==7)wheel_primes[0]=index;if(p==11)wheel_primes[1]=index;if(p==13)wheel_primes[2]=index;
  if(p>PgnPreMax)for(unsigned chunk=0;chunk<((1u<<19)/p+2+255)/256;++chunk){item_pidx.push_back(index);item_k0.push_back(chunk);}
  roots1.push_back(uint32_t((((1ULL<<19)/8)*30)%p));roots92.push_back(uint32_t((92ULL*((1ULL<<19)/8)*30)%p));
 }
 if(primes.size()!=4200)return 2;
 const auto hostPrefix=pgn_event210::makePrefix(primes);
 std::ifstream input("event-wheel210-prefix.bin",std::ios::binary|std::ios::ate);
 if(!input||input.tellg()!=std::streamoff(hostPrefix.size()*4))return 8;
 std::vector<uint32_t> independent(hostPrefix.size());input.seekg(0);
 if(!input.read(reinterpret_cast<char*>(independent.data()),independent.size()*4)||independent!=hostPrefix)return 8;
 uint32_t* eventAllocation=nullptr;CU(pgn_event210::upload(primes,&eventAllocation));

 const uint32_t classes[8]={1,7,11,13,17,19,23,29};int8_t index[30];std::memset(index,-1,sizeof(index));uint32_t permutation[30]{},inverse[30]{};
 for(unsigned i=0;i<8;++i)index[classes[i]]=int8_t(i);
 for(unsigned p=0;p<30;++p)if(index[p]>=0){for(unsigned j=0;j<8;++j)permutation[p]|=1u<<((p*classes[j])%30);for(unsigned x=1;x<30;++x)if(p*x%30==1)inverse[p]=x;}
 CU(cudaMemcpyToSymbol(c30_clsidx,index,sizeof(index)));CU(cudaMemcpyToSymbol(c30_perm,permutation,sizeof(permutation)));CU(cudaMemcpyToSymbol(c30_pinv,inverse,sizeof(inverse)));
 const uint64_t* presieve[5]{};
 for(unsigned group=0;group<PGN_PRESIEVE_GROUPS;++group){const auto table=pgnMakePreTable(group);uint64_t* device=nullptr;CU(cudaMalloc(&device,table.size()*8));CU(cudaMemcpy(device,table.data(),table.size()*8,cudaMemcpyHostToDevice));presieve[group]=device;}
 CU(cudaMemcpyToSymbol(pgn_pre_tables,presieve,sizeof(presieve)));
 uint64_t *dp=nullptr,*di=nullptr,*dr=nullptr;uint32_t *dit=nullptr,*dchunks=nullptr,*dw=nullptr,*droot1=nullptr,*droot92=nullptr;
 CU(cudaMalloc(&dp,primes.size()*8));CU(cudaMemcpy(dp,primes.data(),primes.size()*8,cudaMemcpyHostToDevice));
 CU(cudaMalloc(&di,reciprocals.size()*8));CU(cudaMemcpy(di,reciprocals.data(),reciprocals.size()*8,cudaMemcpyHostToDevice));
 CU(cudaMalloc(&dr,r64.size()*8));CU(cudaMemcpy(dr,r64.data(),r64.size()*8,cudaMemcpyHostToDevice));
 CU(cudaMalloc(&dit,item_pidx.size()*4));CU(cudaMemcpy(dit,item_pidx.data(),item_pidx.size()*4,cudaMemcpyHostToDevice));
 CU(cudaMalloc(&dchunks,item_k0.size()*4));CU(cudaMemcpy(dchunks,item_k0.data(),item_k0.size()*4,cudaMemcpyHostToDevice));
 CU(cudaMalloc(&dw,sizeof(wheel_primes)));CU(cudaMemcpy(dw,wheel_primes,sizeof(wheel_primes),cudaMemcpyHostToDevice));
 CU(cudaMalloc(&droot1,roots1.size()*4));CU(cudaMemcpy(droot1,roots1.data(),roots1.size()*4,cudaMemcpyHostToDevice));
 CU(cudaMalloc(&droot92,roots92.size()*4));CU(cudaMemcpy(droot92,roots92.data(),roots92.size()*4,cudaMemcpyHostToDevice));
 PgnWalkGraphBuffers b{};b.primes=dp;b.invp=di;b.r64=dr;b.item_pidx=dit;b.item_k0=dchunks;b.item_count=unsigned(item_pidx.size());b.wheel_primes=dw;b.blocks_per_slot=1;
 uint64_t *reference=nullptr,*candidate=nullptr;CU(cudaMalloc(&reference,Words*8));CU(cudaMalloc(&candidate,Words*8));
 PgnWalkDescriptor* desc=nullptr;PgnWalkGraphState* state=nullptr;CU(cudaMalloc(&desc,sizeof(PgnWalkDescriptor)));CU(cudaMalloc(&state,sizeof(PgnWalkGraphState)));
 const PgnWalkGraphState initial{0,1,0};CU(cudaMemcpy(state,&initial,sizeof(initial),cudaMemcpyHostToDevice));
 CU(cudaFuncSetAttribute(referenceMark92,cudaFuncAttributeMaxDynamicSharedMemorySize,65536));CU(cudaFuncSetAttribute(pgn_graph_mark,cudaFuncAttributeMaxDynamicSharedMemorySize,65536));
 std::vector<uint64_t> expected(Words),got(Words);
 // Aligned128-bit origins: high10, high47, and low64 carry within thisbitmap.
 const uint64_t origins[3][2]={{15532549262904483830ULL,10ULL},{11594028535651074028ULL,47ULL},{18446744073705551600ULL,10ULL}};
 for(unsigned i=0;i<3;++i){
  const uint64_t low=origins[i][0],high=origins[i][1];if((low%30+(high%30)*16)%30)return 2;
  b.bitmaps=reference;b.root_steps=droot92;referenceMark92<<<82,512,65536>>>(low,high,b);CU(cudaGetLastError());CU(cudaDeviceSynchronize());
  const PgnWalkDescriptor descriptor{low,high,1,1};CU(cudaMemcpy(desc,&descriptor,sizeof(descriptor),cudaMemcpyHostToDevice));
  b.bitmaps=candidate;b.root_steps=droot1;pgn_graph_mark<<<82,512,65536>>>(desc,state,b,0);CU(cudaGetLastError());CU(cudaDeviceSynchronize());
  CU(cudaMemcpy(expected.data(),reference,Words*8,cudaMemcpyDeviceToHost));CU(cudaMemcpy(got.data(),candidate,Words*8,cudaMemcpyDeviceToHost));
  if(got!=expected){std::fprintf(stderr,"FULL_BITMAP_MAPPING_MISMATCH origin%u\n",i);return 4;}
  got[Words/2]^=1ULL;if(got==expected)return 5;
  std::printf("origin=%u exact_words=%llu all512tiles=1 poison_detected=1\n",i,static_cast<unsigned long long>(Words));
 }
 std::puts("SMALLWORD7_ORIGINAL_UNFILTERED_REFERENCE_FULL_BITMAP_POISON_PASS");return 0;
}
