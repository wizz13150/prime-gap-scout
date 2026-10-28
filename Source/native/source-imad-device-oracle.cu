#include <cuda_runtime.h>
#include "barrett70-exact.cuh"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <vector>
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"CUDA %s:%d %s\n",__FILE__,__LINE__,cudaGetErrorString(e));std::exit(2);}}while(0)
struct Raw {uint32_t w[13];};
__global__ void rawWords(const Raw* in,uint32_t* out,unsigned n){
 const unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;
 const auto* v=in[i].w;const pgn_barrett70::U96 mod{{v[8],v[9],10}},recip{{v[5],v[6],v[7]}};
 const auto r=pgn_barrett70::reduceSquaredWords(v[0],v[1],v[2],v[3],v[4],mod,recip);
 for(unsigned k=0;k<3;++k)out[4+i*3+k]=r.w[k];
}
__global__ void pointFlags(const uint64_t* in,uint32_t* out,unsigned n){
 const unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)out[4+i]=unsigned(pgn_barrett70::test(in[i]));
}
struct Header {char magic[8];uint32_t count,size;};
static FILE* openFixture(const char* path,Header& h,const char* magic,unsigned stride){
 FILE* f=std::fopen(path,"rb");if(!f){std::perror(path);std::exit(3);}
 if(std::fread(&h,1,sizeof(h),f)!=sizeof(h)||std::memcmp(h.magic,magic,8)||!h.count||h.count>200000||h.size!=stride){std::fprintf(stderr,"Fixture header invalid\n");std::exit(3);}return f;
}
static void readExact(FILE* f,void* p,size_t bytes){if(std::fread(p,1,bytes,f)!=bytes){std::fprintf(stderr,"Fixture truncated\n");std::exit(3);}}
static void eof(FILE* f){if(std::fgetc(f)!=EOF){std::fprintf(stderr,"Trailing fixture bytes\n");std::exit(3);}std::fclose(f);}
static void guards(const std::vector<uint32_t>& out,unsigned payload){for(unsigned i=0;i<4;++i)if(out[i]!=0xa5a5a5a5u||out[4+payload+i]!=0xa5a5a5a5u){std::fprintf(stderr,"Output sentinel corrupted\n");std::exit(5);}}
int main(int argc,char** argv){
 if(argc<3||argc>4)return 3;const bool poison=argc==4&&std::strcmp(argv[3],"--poison-expected")==0;
 Header h{};FILE* f=openFixture(argv[1],h,"B70MAD01",52);std::vector<Raw> words(h.count);readExact(f,words.data(),words.size()*sizeof(Raw));eof(f);
 if(poison)words[0].w[10]^=1;
 Raw* dw=nullptr;uint32_t* dout=nullptr;const unsigned payload=h.count*3;
 CK(cudaMalloc(&dw,words.size()*sizeof(Raw)));CK(cudaMalloc(&dout,(payload+8)*sizeof(uint32_t)));
 CK(cudaMemcpy(dw,words.data(),words.size()*sizeof(Raw),cudaMemcpyHostToDevice));CK(cudaMemset(dout,0xa5,(payload+8)*sizeof(uint32_t)));
 rawWords<<<(h.count+127)/128,128>>>(dw,dout,h.count);CK(cudaGetLastError());
 std::vector<uint32_t> out(payload+8);CK(cudaMemcpy(out.data(),dout,out.size()*sizeof(uint32_t),cudaMemcpyDeviceToHost));guards(out,payload);
 std::vector<Raw> back(words.size());CK(cudaMemcpy(back.data(),dw,back.size()*sizeof(Raw),cudaMemcpyDeviceToHost));if(std::memcmp(words.data(),back.data(),words.size()*sizeof(Raw))){std::fprintf(stderr,"Input modified\n");return 5;}
 unsigned mismatches=0;for(unsigned i=0;i<h.count;++i)for(unsigned k=0;k<3;++k)mismatches+=out[4+i*3+k]!=words[i].w[10+k];
 CK(cudaFree(dout));CK(cudaFree(dw));
 if(poison){if(mismatches!=1){std::fprintf(stderr,"Poison must cause exactly one observed mismatch, got%u\n",mismatches);return 6;}std::printf("{\"state\":\"GPU_EXPECTED_POISON_ONE_MISMATCH_OBSERVED\",\"raw_cases\":%u}\n",h.count);return 0;}
 if(mismatches){std::fprintf(stderr,"Raw PTX word mismatches=%u\n",mismatches);return 7;}
 const unsigned wordCount=h.count;f=openFixture(argv[2],h,"B70POINT",0);std::vector<uint64_t> points(h.count);std::vector<uint32_t> expected(h.count);readExact(f,points.data(),points.size()*sizeof(uint64_t));readExact(f,expected.data(),expected.size()*sizeof(uint32_t));eof(f);
 uint64_t* dp=nullptr;CK(cudaMalloc(&dp,points.size()*sizeof(uint64_t)));CK(cudaMalloc(&dout,(h.count+8)*sizeof(uint32_t)));CK(cudaMemcpy(dp,points.data(),points.size()*sizeof(uint64_t),cudaMemcpyHostToDevice));CK(cudaMemset(dout,0xa5,(h.count+8)*sizeof(uint32_t)));
 pointFlags<<<(h.count+127)/128,128>>>(dp,dout,h.count);CK(cudaGetLastError());out.resize(h.count+8);CK(cudaMemcpy(out.data(),dout,out.size()*sizeof(uint32_t),cudaMemcpyDeviceToHost));guards(out,h.count);
 for(unsigned i=0;i<h.count;++i)if(out[4+i]!=expected[i]){std::fprintf(stderr,"Euler point mismatch at%u\n",i);return 8;}
 std::vector<uint64_t> pointsBack(points.size());CK(cudaMemcpy(pointsBack.data(),dp,pointsBack.size()*sizeof(uint64_t),cudaMemcpyDeviceToHost));if(pointsBack!=points){std::fprintf(stderr,"Point input modified\n");return 9;}
 CK(cudaFree(dout));CK(cudaFree(dp));
 std::printf("{\"state\":\"GPU_SOURCE_IMAD_WORDS_BIGINT_EULER_AND_GUARDS_PASS\",\"raw_cases\":%u,\"Euler_points\":%u,\"input_immutable\":true,\"prime_certificate\":false}\n",wordCount,h.count);
}
