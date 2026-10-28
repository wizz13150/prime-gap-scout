#include <cuda_runtime.h>
#include "barrett70-exact.cuh"
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <vector>
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"CUDA %s\n",cudaGetErrorString(e));std::exit(2);}}while(0)
struct Record{uint32_t w[8];};
struct Header{char magic[8];uint32_t count,stride;};
__global__ void normalize(const Record* input,uint32_t* output,unsigned count){
 unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=count)return;
 const auto* p=input[i].w;const pgn_barrett70::U96 n{{p[0],p[1],10}},a{{p[2],p[3],p[4]}};
 const auto r=pgn_barrett70::normalizeFinal12(a,n);
 for(unsigned k=0;k<3;++k)output[4+3*i+k]=r.w[k];
}
int main(int argc,char**argv){
 if(argc<2||argc>3)return 3;const bool poison=argc==3&&std::strcmp(argv[2],"--poison-expected")==0;
 FILE* f=std::fopen(argv[1],"rb");if(!f)return 3;Header h{};
 if(std::fread(&h,1,sizeof(h),f)!=sizeof(h)||std::memcmp(h.magic,"NORM12V1",8)||!h.count||h.count>2000000||h.stride!=32)return 3;
 std::vector<Record> input(h.count);if(std::fread(input.data(),32,h.count,f)!=h.count||std::fgetc(f)!=EOF)return 3;std::fclose(f);
 Record* di=nullptr;uint32_t* out=nullptr;const size_t bytes=(size_t(h.count)*3+8)*4;
 CK(cudaMalloc(&di,input.size()*sizeof(Record)));CK(cudaMalloc(&out,bytes));CK(cudaMemcpy(di,input.data(),input.size()*sizeof(Record),cudaMemcpyHostToDevice));CK(cudaMemset(out,0xa5,bytes));
 normalize<<<(h.count+127)/128,128>>>(di,out,h.count);CK(cudaGetLastError());
 std::vector<uint32_t> got(size_t(h.count)*3+8);CK(cudaMemcpy(got.data(),out,bytes,cudaMemcpyDeviceToHost));
 for(unsigned i=0;i<4;++i)if(got[i]!=0xa5a5a5a5u||got[4+size_t(h.count)*3+i]!=0xa5a5a5a5u)return 4;
 std::vector<Record> back(h.count);CK(cudaMemcpy(back.data(),di,back.size()*sizeof(Record),cudaMemcpyDeviceToHost));if(std::memcmp(back.data(),input.data(),input.size()*sizeof(Record)))return 5;
 unsigned mismatches=0;if(poison)input[0].w[5]^=1;
 for(unsigned i=0;i<h.count;++i)for(unsigned k=0;k<3;++k)mismatches+=got[4+size_t(i)*3+k]!=input[i].w[5+k];
 CK(cudaFree(di));CK(cudaFree(out));
 if(mismatches!=(poison?1u:0u)){std::fprintf(stderr,"mismatches=%u\n",mismatches);return 6;}
 std::printf("{\"state\":\"%s\",\"cases\":%u,\"all96bit_words_exact\":true,\"input_immutable\":true,\"guards\":true,\"production_gain_claim\":false}\n",poison?"PREFIX11_EXPECTED_POISON_ONE_MISMATCH_OBSERVED":"PREFIX11_ALL_DIRECT_CANONICAL_RESIDUES_EXACT",h.count);
}
