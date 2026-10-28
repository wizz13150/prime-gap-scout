Corresponding historical source for bin/compat
=============================================
The40 manifest-listed common files are the original Ubuntu960/Windows960
inputs. For Windows954 replace only continuous-gpu-runtime.cu with the
windows954 overlay. The three original manifests bind all source bytes.
CUDA12.8, C++17, RDC+DLTO, cudadevrt, K64 default and original defines apply.
Windows: run in a Visual Studio x64 developer prompt; use supported MSVC.
Linux: use GCC13 (e.g. --compiler /usr/bin/g++-13).
Example: python build_compat.py --arch 86 --floor 954 --out worker-review.exe.
See ../BUILD.txt for CUDA and driver setup. Main build.py builds the current
workers; this script is only for reconstructing historical source variants.
Rebuilding does NOT guarantee the original executable SHA-256. Keep the
shipped exact bin/compat binaries/sidecars/runtime libraries for old resumes.
Never rename a rebuilt image to pretend it matches a pinned checkpoint.
Preserve ../THIRD-PARTY-NOTICES.txt and ../THIRD-PARTY-LICENSES.
