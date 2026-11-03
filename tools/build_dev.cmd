@echo off
rem Development build of a Cycles worktree with Ninja and sccache.
rem   build_dev.cmd <worktree> <install dir> [configure]
rem Kernels for the local GPU only (sm_86) and the local CPU only: a
rem shipping build still goes through the full Visual Studio build.
rem Tools in E:\devtools (Ninja 1.12.1, sccache 0.10.0), cache on E:.
setlocal
set WT=%~1
set INST=%~2
if "%WT%"=="" (echo usage: build_dev.cmd ^<worktree^> ^<install dir^> [configure] & exit /b 2)
call "D:\VS\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set PATH=E:\devtools\ninja;E:\devtools\sccache;%PATH%
set SCCACHE_DIR=E:\devtools\sccache-cache
set SCCACHE_CACHE_SIZE=60G
set TEMP=E:\claude_temp\hdCycles\tmp
set TMP=E:\claude_temp\hdCycles\tmp
cd /d "%WT%" || exit /b 1
if "%~3"=="configure" (
  cmake -S . -B build-dev -G Ninja -DCMAKE_BUILD_TYPE=Release ^
    -DCMAKE_C_COMPILER_LAUNCHER=sccache -DCMAKE_CXX_COMPILER_LAUNCHER=sccache ^
    -DHOUDINI_ROOT="E:/Side Effects Software/Houdini22.0.368" ^
    -DOPTIX_ROOT_DIR="C:/ProgramData/NVIDIA Corporation/OptiX SDK 9.1.0" ^
    -DCMAKE_INSTALL_PREFIX="%INST%" ^
    -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=ON -DWITH_CYCLES_USD=ON -DWITH_CYCLES_OSL=ON -DWITH_CYCLES_EMBREE=ON ^
    -DWITH_CYCLES_DEVICE_CUDA=ON -DWITH_CYCLES_DEVICE_OPTIX=ON -DWITH_CYCLES_CUDA_BINARIES=ON ^
    -DCYCLES_CUDA_BINARIES_ARCH=sm_86 -DCUDA_NVCC_FLAGS=--split-compile=32 ^
    -DWITH_CYCLES_DEVICE_HIP=OFF -DWITH_CYCLES_HIP_BINARIES=OFF -DWITH_CYCLES_DEVICE_ONEAPI=OFF ^
    -DWITH_CYCLES_NATIVE_ONLY=ON -DWITH_CYCLES_LOGGING=OFF || exit /b 1
)
rem Below normal priority and 32 jobs: Houdini renders may share the machine.
start "" /belownormal /wait /b cmake --build build-dev --target install -- -j 32
set RC=%ERRORLEVEL%
sccache --show-stats | findstr /r /c:"Cache hits rate" /c:"Cache misses" /c:"Compilations"
exit /b %RC%
