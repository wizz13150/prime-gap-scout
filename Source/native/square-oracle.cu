#include <cuda_runtime.h>
#include "barrett70-baseline.cuh"
#include "barrett70-exact.cuh"
#include <vector>
#include <fstream>
#include <cstdio>
#include <cstring>
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"CUDA:%s\n",cudaGetErrorString(e));return 2;}}while(0)
struct SquareCase{uint64_t low;uint32_t a[3],expected[3];};
struct Residue{uint32_t w[3];};
struct EulerCase{uint64_t low;uint32_t expected,padding;};
template<bool New> __global__ void squares(const SquareCase* in,Residue* out,unsigned count){
 unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=count)return;
 if constexpr(New){const pgn_barrett70::U96 n{{uint32_t(in[i].low),uint32_t(in[i].low>>32),10}},a{{in[i].a[0],in[i].a[1],in[i].a[2]}};auto r=pgn_barrett70::squareLazy(a,n,pgn_barrett70::reciprocal160(n));out[i]={{r.w[0],r.w[1],r.w[2]}};}
 else{const pgn_barrett70_base::U96 n{{uint32_t(in[i].low),uint32_t(in[i].low>>32),10}},a{{in[i].a[0],in[i].a[1],in[i].a[2]}};auto r=pgn_barrett70_base::squareLazy(a,n,pgn_barrett70_base::reciprocal160(n));out[i]={{r.w[0],r.w[1],r.w[2]}};}
}
template<bool New> __global__ void eulers(const EulerCase* in,unsigned* out,unsigned count){unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i<count){if constexpr(New)out[i]=pgn_barrett70::test(in[i].low);else out[i]=pgn_barrett70_base::test(in[i].low);}}
static bool greater(const Residue&a,const Residue&b){for(int k=2;k>=0;--k)if(a.w[k]!=b.w[k])return a.w[k]>b.w[k];return true;}
static void subtract(Residue&a,const Residue&b){uint64_t borrow=0;for(int k=0;k<3;++k){uint64_t v=uint64_t(b.w[k])+borrow;uint32_t x=a.w[k];a.w[k]=uint32_t(uint64_t(x)-v);borrow=uint64_t(x)<v;}}
int main(int argc,char**argv){
 if(argc!=3)return 1;std::ifstream f(argv[1],std::ios::binary|std::ios::ate);if(!f||f.tellg()>64*1024*1024)return 1;f.seekg(0);char magic[8];unsigned count;f.read(magic,8);f.read(reinterpret_cast<char*>(&count),4);if(std::memcmp(magic,"FUSESQ1\0",8)||!count||count>1000000)return 1;std::vector<SquareCase> input(count);f.read(reinterpret_cast<char*>(input.data()),count*sizeof(SquareCase));if(!f)return 1;
 SquareCase* dIn;Residue*dOut;CK(cudaMalloc(&dIn,count*sizeof(SquareCase)));CK(cudaMalloc(&dOut,count*sizeof(Residue)));CK(cudaMemcpy(dIn,input.data(),count*sizeof(SquareCase),cudaMemcpyHostToDevice));std::vector<Residue> out(count),baseline;
 for(unsigned mode=0;mode<2;++mode){if(mode)squares<true><<<(count+255)/256,256>>>(dIn,dOut,count);else squares<false><<<(count+255)/256,256>>>(dIn,dOut,count);CK(cudaGetLastError());CK(cudaMemcpy(out.data(),dOut,count*sizeof(Residue),cudaMemcpyDeviceToHost));
  for(unsigned i=0;i<count;++i){Residue n{{uint32_t(input[i].low),uint32_t(input[i].low>>32),10}},bound{};uint64_t carry=0;for(int k=0;k<3;++k){uint64_t v=uint64_t(n.w[k])*6+carry;bound.w[k]=uint32_t(v);carry=v>>32;}
   Residue r=out[i];if(greater(r,bound)){std::fprintf(stderr,"Lazy bound mode%u row%u\n",mode,i);return 3;}unsigned corrections=0;while(greater(r,n)){subtract(r,n);if(++corrections>5)return 3;}
   if(std::memcmp(r.w,input[i].expected,12)){std::fprintf(stderr,"Independent Python modular-square mismatch mode%u row%u\n",mode,i);return 3;}}
  if(!mode)baseline=out;else if(std::memcmp(baseline.data(),out.data(),count*sizeof(Residue))){std::fprintf(stderr,"Raw lazy representation differs\n");return 4;}
 }
 CK(cudaFree(dOut));CK(cudaFree(dIn));
 std::ifstream e(argv[2],std::ios::binary);unsigned ec;char em[8];e.read(em,8);e.read(reinterpret_cast<char*>(&ec),4);if(std::memcmp(em,"RNSEUL1\0",8)||!ec||ec>262144)return 1;std::vector<EulerCase> ei(ec);
 for(unsigned i=0;i<ec;++i){unsigned char row[144];e.read(reinterpret_cast<char*>(row),144);if(!e)return 1;std::memcpy(&ei[i].low,row,8);std::memcpy(&ei[i].expected,row+8,4);ei[i].padding=0;}
 EulerCase* de;unsigned* answers;CK(cudaMalloc(&de,ec*sizeof(EulerCase)));CK(cudaMalloc(&answers,ec*4));CK(cudaMemcpy(de,ei.data(),ec*sizeof(EulerCase),cudaMemcpyHostToDevice));std::vector<unsigned> got(ec);cudaEvent_t began,ended;CK(cudaEventCreate(&began));CK(cudaEventCreate(&ended));float elapsed[2]{};
 for(unsigned mode=0;mode<2;++mode){if(mode)eulers<true><<<(ec+255)/256,256>>>(de,answers,ec);else eulers<false><<<(ec+255)/256,256>>>(de,answers,ec);CK(cudaGetLastError());CK(cudaMemcpy(got.data(),answers,ec*4,cudaMemcpyDeviceToHost));for(unsigned i=0;i<ec;++i)if(got[i]!=ei[i].expected){std::fprintf(stderr,"Python Euler mismatch mode%u row%u\n",mode,i);return 5;}
  CK(cudaEventRecord(began));for(unsigned repeat=0;repeat<30;++repeat){if(mode)eulers<true><<<(ec+255)/256,256>>>(de,answers,ec);else eulers<false><<<(ec+255)/256,256>>>(de,answers,ec);}CK(cudaGetLastError());CK(cudaEventRecord(ended));CK(cudaEventSynchronize(ended));CK(cudaEventElapsedTime(&elapsed[mode],began,ended));}
 std::printf("{\"state\":\"FUSED_SQUARE_RAW_LAZY_AND_PYTHON_SQUARE_EULER_EXACT_PASS\",\"square_cases\":%u,\"euler_cases\":%u,\"warm_30repeat_component_ms_base_new\":[%.6f,%.6f],\"scope\":\"private_component_only_no_mining_gain_or_credit_claim\"}\n",count,ec,elapsed[0],elapsed[1]);CK(cudaFree(answers));CK(cudaFree(de));CK(cudaEventDestroy(ended));CK(cudaEventDestroy(began));
}
