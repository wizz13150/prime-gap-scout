#include <cuda_runtime.h>
#include "barrett70-exact.cuh"
#include <cstdio>
#include <cstdlib>
#include <vector>
#define CUDA_CHECK(expression) do { const auto e=(expression); if(e!=cudaSuccess){ \
 std::fprintf(stderr,"CUDA:%s:%d:%s\n",__FILE__,__LINE__,cudaGetErrorString(e));std::exit(2);}}while(0)
struct Input { pgn_barrett70::U96 a,b; };
struct Output { pgn_barrett70::U96 result; unsigned borrow; };
__global__ void evaluate(const Input* input,Output* output,unsigned count){
 const unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=count)return;
 auto a=input[i].a;const unsigned borrow=pgn_barrett70::sub(a,input[i].b);output[i]={a,borrow};
}
static std::uint64_t random64(std::uint64_t& state){
 state+=0x9e3779b97f4a7c15ULL;auto x=state;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;
 x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);
}
int main(){
 std::vector<Input> in;const unsigned words[]={0,1,2,0x7fffffffu,0x80000000u,0xfffffffeu,0xffffffffu};
 std::vector<pgn_barrett70::U96> corners;
 for(auto a:words)for(auto b:words)for(auto c:words)corners.push_back({{a,b,c}});
 for(const auto& a:corners)for(const auto& b:corners)in.push_back({a,b});
 std::uint64_t random=0x50474e424f525231ULL;
 for(unsigned i=0;i<262144;++i){Input a{};for(unsigned k=0;k<3;++k){a.a.w[k]=unsigned(random64(random));a.b.w[k]=unsigned(random64(random));}in.push_back(a);}
 Input* dIn=nullptr;Output* dOut=nullptr;CUDA_CHECK(cudaMalloc(&dIn,in.size()*sizeof(Input)));
 CUDA_CHECK(cudaMalloc(&dOut,in.size()*sizeof(Output)));CUDA_CHECK(cudaMemcpy(dIn,in.data(),in.size()*sizeof(Input),cudaMemcpyHostToDevice));
 evaluate<<<unsigned((in.size()+255)/256),256>>>(dIn,dOut,unsigned(in.size()));CUDA_CHECK(cudaGetLastError());
 std::vector<Output> out(in.size());CUDA_CHECK(cudaMemcpy(out.data(),dOut,out.size()*sizeof(Output),cudaMemcpyDeviceToHost));
 for(std::size_t i=0;i<in.size();++i){
  // Independent scalar reference; no PTX, no CUDA host branch call.
  std::uint64_t borrow=0;unsigned expected[3]{};
  for(unsigned k=0;k<3;++k){const auto a=std::uint64_t(in[i].a.w[k]);const auto b=std::uint64_t(in[i].b.w[k])+borrow;
   expected[k]=unsigned(a-b);borrow=unsigned(a<b);}
  bool equal=out[i].borrow==borrow;for(unsigned k=0;k<3;++k)equal=equal&&out[i].result.w[k]==expected[k];
  if(!equal){std::fprintf(stderr,"96bit subtraction mismatch at %zu\n",i);return 3;}
 }
 CUDA_CHECK(cudaFree(dOut));CUDA_CHECK(cudaFree(dIn));
 std::printf("{\"state\":\"GPU_PRIMITIVE_ORACLE_PASS\",\"cases\":%zu,\"scope\":\"arithmetic_only_no_mining_credit\"}\n",in.size());
}
