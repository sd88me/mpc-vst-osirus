cmake_minimum_required(VERSION 3.15)
project(osirus_mpc VERSION 0.1.0 LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# Everything hidden, no STB_GNU_UNIQUE symbols: osirus.so must be unloadable (glibc pins a DSO exporting a UNIQUE symbol
# NODELETE) and export nothing but VSTPluginMain. build.sh merges the libraries below into one archive.
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fvisibility=hidden -fvisibility-inlines-hidden -fno-gnu-unique")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -fvisibility=hidden")

# gearmulator pieces the Virus emulation needs (vendored in src/gearmulator, see src/VENDORED.md)
set(GM ${CMAKE_CURRENT_SOURCE_DIR}/src/gearmulator)
set(ASMJIT_STATIC TRUE)
set(ASMJIT_NO_INSTALL TRUE)
set(BUILD_SHARED_LIBS OFF)
add_subdirectory(${GM}/dsp56300/asmjit ${CMAKE_BINARY_DIR}/asmjit)
add_subdirectory(${GM}/dsp56300/vtuneSdk ${CMAKE_BINARY_DIR}/vtuneSdk)
add_subdirectory(${GM}/dsp56300/dsp56kBase ${CMAKE_BINARY_DIR}/dsp56kBase)
add_subdirectory(${GM}/dsp56300/dsp56kEmu ${CMAKE_BINARY_DIR}/dsp56kEmu)
add_subdirectory(${GM}/baseLib ${CMAKE_BINARY_DIR}/baseLib)
add_subdirectory(${GM}/libresample ${CMAKE_BINARY_DIR}/libresample)
add_subdirectory(${GM}/synthLib ${CMAKE_BINARY_DIR}/synthLib)
add_subdirectory(${GM}/virusLib ${CMAKE_BINARY_DIR}/virusLib)

add_executable(osirus_probe test/probe.cpp)
target_include_directories(osirus_probe PRIVATE ${GM} ${GM}/dsp56300)
target_link_libraries(osirus_probe PRIVATE virusLib synthLib baseLib)

# The engine: schwung-virus's plugin glue (src/dsp), in-process. build.sh links it with wrapper/vst2_wrap.c into osirus.so.
# MPC_VST: checkout of mpc-vst-plugins (wrapper/engine.h)
if(NOT MPC_VST)
  set(MPC_VST $ENV{HOME}/mpc-vst-plugins)
endif()
add_library(osirus_dsp STATIC src/dsp/virus_plugin.cpp src/dsp/program_selection.cpp src/dsp/mpc_engine.cpp)
target_include_directories(osirus_dsp PUBLIC ${GM} ${GM}/dsp56300 src/dsp ${MPC_VST}/wrapper)
target_link_libraries(osirus_dsp PUBLIC virusLib synthLib baseLib)

add_executable(osirus_engine_test test/engine_test.cpp)
target_link_libraries(osirus_engine_test PRIVATE osirus_dsp)
