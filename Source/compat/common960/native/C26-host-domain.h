#pragma once
// Oracle-only HOST admission. No CUDA API and no changed device trap.
#include <cstdint>
namespace c26_host_domain {
struct OriginCase {const char* name;uint64_t low,high;};
inline constexpr OriginCase Cases[]={
    {"H10-baseline",15532549262904483830ULL,10ULL},
    {"H10-logicalY-carry",UINT64_MAX-1500000000ULL,10ULL},
    {"H10-rounding-borrow",1ULL,10ULL},
    {"H10-interior-half-carry",UINT64_MAX-4000000ULL,10ULL}
};
// Retained counterexample: CPU rejection only, NEVER part of launch Cases.
inline constexpr OriginCase RejectedH95={
    "REJECT-H95-logicalY-carry",UINT64_MAX-1500000000ULL,(1ULL<<30)+47};
constexpr uint64_t BlockNumbers=30ULL<<25;
constexpr uint64_t CohortNumbers=32ULL*((1ULL<<19)/8)*30ULL;
constexpr uint64_t HalfNumbers=983040ULL;
static_assert(CohortNumbers*16==BlockNumbers && HalfNumbers*64==CohortNumbers,
              "Exact native class30 cohort/half extent");
struct DomainProof {
    uint64_t originLow=0,originHigh=0,lastLow=0,lastHigh=0,span=0;
    bool borrowed=false;
    unsigned halfChecks=0;
    const char* failure="unvalidated";
};
inline bool addWithinTiny(uint64_t low,uint64_t high,uint64_t delta,
                          uint64_t& outLow,uint64_t& outHigh){
    outLow=low+delta;
    const uint64_t carry=uint64_t(outLow<low);
    if(high>47 || carry>47-high)return false;
    outHigh=high+carry;return true;
}
inline bool validate(const OriginCase& c,unsigned blocks,DomainProof& proof){
    proof={};
    if(blocks!=1&&blocks!=2&&blocks!=65){proof.failure="shape";return false;}
    // This oracle's entire positive fixture family is specifically H10.
    // Both63bit/high0 and95bit/high>=2^30 fixtures are rejected on the HOST.
    if(c.high!=10){proof.failure="expected-H10-descriptor";return false;}
    const uint64_t remainder=(c.low%30+(c.high%30)*16)%30;
    proof.borrowed=c.low<remainder;
    if(proof.borrowed && !c.high){proof.failure="origin-underflow";return false;}
    proof.originLow=c.low-remainder;
    proof.originHigh=c.high-uint64_t(proof.borrowed);
    proof.span=uint64_t(blocks)*BlockNumbers;
    // Includes the final class30 residue29 and all logicalY/cohort/half carries.
    if(!addWithinTiny(proof.originLow,proof.originHigh,proof.span-1,
                      proof.lastLow,proof.lastHigh)){
        proof.failure="full-bitmap-Tiny-high47";return false;
    }
    for(unsigned y=0;y<blocks;++y)for(unsigned cohort=0;cohort<16;++cohort)
      for(unsigned half=0;half<64;++half){
        const uint64_t offset=uint64_t(y)*BlockNumbers+
            uint64_t(cohort)*CohortNumbers+uint64_t(half)*HalfNumbers;
        if(offset+HalfNumbers>proof.span){proof.failure="extent";return false;}
        uint64_t lo=0,hi=0;
        // +1 is the real phase/root initialization input. The half's last
        // integer closes the full span, including half-interior low64 carry.
        if(!addWithinTiny(proof.originLow,proof.originHigh,offset+1,lo,hi)||
           !addWithinTiny(proof.originLow,proof.originHigh,
                          offset+HalfNumbers-1,lo,hi)){
            proof.failure="cohort-half-Tiny-high47";return false;
        }
        ++proof.halfChecks;
      }
    proof.failure=nullptr;return true;
}
inline bool validateAll(unsigned blocks){
    for(const auto& c:Cases){DomainProof proof;if(!validate(c,blocks,proof))return false;}
    return true;
}
} // namespace c26_host_domain
