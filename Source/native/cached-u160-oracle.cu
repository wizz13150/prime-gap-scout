#include <cuda_runtime.h>
#include "stateful-u160-live.cuh"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"CUDA %d %s\n",__LINE__,cudaGetErrorString(e));std::exit(2);}}while(0)
struct Header{char magic[8];uint32_t count,stride;};
struct Step{uint32_t w[11];};
struct Answer{uint32_t w[9];};
__global__ void sequenceKernel(const Step*rows,Answer*out,unsigned groups){
 const unsigned group=blockIdx.x*blockDim.x+threadIdx.x;if(group>=groups)return;
 pgn_stateful_u160::State numerical{},native{};
 for(unsigned k=0;k<2048;++k){
  const unsigned i=group*2048+k;const auto row=rows[i];
  if(row.w[0]){numerical={};native={};}
  if(row.w[3]==1){numerical.inverse=0;native.inverse=0;}
  else if(row.w[3]==2){numerical.inverse=1e30f;native.inverse=1e30f;}
  const uint64_t low=(uint64_t(row.w[2])<<32)|row.w[1];bool hit=false;
  const auto rem=pgn_stateful_u160::prepare(numerical,low,&hit);Answer a{};
  for(unsigned j=0;j<3;++j){a.w[j]=numerical.u.w[j];a.w[3+j]=rem.w[j];}
  a.w[6]=pgn_barrett70::testWithReciprocal(low,numerical.u,rem,numerical.inverse);
  // An independent state exercises the actual odd/even native predicate;
  // even points do not update it. Both paths have independent bigint truth.
  a.w[7]=pgn_stateful_u160::test(low,native);a.w[8]=hit;out[i+1]=a;
 }
}
int main(int argc,char**argv){
 if(argc<2||argc>3)return 3;const bool poison=argc==3&&std::strcmp(argv[2],"--poison-expected")==0;
 FILE*f=std::fopen(argv[1],"rb");if(!f)return 3;Header h{};
 if(std::fread(&h,1,sizeof(h),f)!=sizeof(h)||std::memcmp(h.magic,"U160LIVE",8)||h.count!=131072||h.stride!=44)return 3;
 std::vector<Step> rows(h.count);if(std::fread(rows.data(),sizeof(Step),rows.size(),f)!=rows.size()||std::fgetc(f)!=EOF)return 3;std::fclose(f);
 for(unsigned i=0;i<h.count;++i)if(rows[i].w[0]!=unsigned(i%2048==0)||rows[i].w[3]>2)return 3;
 cudaDeviceProp property{};CK(cudaGetDeviceProperties(&property,0));
 std::printf("[pgn-physical-resource-proof] SM_shared_bytes=%zu driver_reserved_per_block=%zu max_threads_SM=%d State_bytes=%zu\n",property.sharedMemPerMultiprocessor,property.reservedSharedMemPerBlock,property.maxThreadsPerMultiProcessor,sizeof(pgn_stateful_u160::State));
 Step*dr=nullptr;Answer*da=nullptr;CK(cudaMalloc(&dr,rows.size()*sizeof(Step)));CK(cudaMalloc(&da,(h.count+2)*sizeof(Answer)));
 CK(cudaMemcpy(dr,rows.data(),rows.size()*sizeof(Step),cudaMemcpyHostToDevice));CK(cudaMemset(da,0xa5,(h.count+2)*sizeof(Answer)));
 sequenceKernel<<<2,32>>>(dr,da,h.count/2048);CK(cudaGetLastError());
 std::vector<Answer> out(h.count+2);CK(cudaMemcpy(out.data(),da,out.size()*sizeof(Answer),cudaMemcpyDeviceToHost));
 for(unsigned k=0;k<9;++k)if(out.front().w[k]!=0xa5a5a5a5u||out.back().w[k]!=0xa5a5a5a5u)return 4;
 unsigned bad=0,hits=0;
 for(unsigned i=0;i<h.count;++i){const auto&a=out[i+1];for(unsigned k=0;k<6;++k)if(a.w[k]!=rows[i].w[4+k])return 5;
  bad+=a.w[6]!=(rows[i].w[10]^unsigned(poison&&i==0));if(a.w[7]!=rows[i].w[10])return 6;hits+=a.w[8]!=0;
 }
 std::vector<Step> back(rows.size());CK(cudaMemcpy(back.data(),dr,back.size()*sizeof(Step),cudaMemcpyDeviceToHost));if(std::memcmp(back.data(),rows.data(),back.size()*sizeof(Step)))return 7;
 CK(cudaFree(da));CK(cudaFree(dr));if(bad!=unsigned(poison))return 8;
 std::printf("{\"state\":\"%s\",\"cases\":%u,\"cache_hits\":%u,\"original_exact_fallbacks\":%u,\"two_independent_state_paths\":true,\"input_immutable\":true,\"mining_credit\":false}\n",poison?"GPU_LIVE_STATE_POISON_ONE_EXPECTED_MISMATCH":"GPU_LIVE_STATE_BIGINT_U_R_BOTH_EULER_PATHS_EXACT",h.count,hits,h.count-hits);
}
