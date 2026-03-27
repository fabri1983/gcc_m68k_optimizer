#!/usr/bin/bash

# Please use the MSYS2 MinGW64 shell, not the UCRT shell nor the MSYS.
# You can check which shell are you at by typing: 
#   echo $MSYSTEM
# Set execution permission (if needed):
#   chmod +x build_plugin_mingw64_windows.sh
#   ./build_plugin_mingw64_windows.sh

# Check if running in MINGW64 environment
if [[ "$MSYSTEM" != "MINGW64" ]]; then
    echo "Error: This script must be run in MINGW64 shell."
    echo "Current MSYSTEM is: $MSYSTEM"
    echo "Please use the MSYS2 MinGW64 shell (not UCRT64, CLANG64, or MSYS)."
    exit 1
fi

# Check if gcc is located at /mingw64/bin/gcc
GCC_PATH=$(which gcc)
if [[ "$GCC_PATH" != "/mingw64/bin/gcc" ]]; then
    echo "Error: gcc is not located at /mingw64/bin/gcc"
    echo "Current gcc path is: $GCC_PATH"
    echo "Try closing and then re open this terminal."
    exit 1
fi

ROOTDIR=`pwd`
M68K_GCC_TOOLCHAIN="$ROOTDIR/toolchain-m68k-elf-gcc"
export PATH=$M68K_GCC_TOOLCHAIN/bin:$PATH

HOST_GCC_VERSION=$(gcc -dumpversion)
echo "Host GCC version: $HOST_GCC_VERSION"
TARGET_GCC_VERSION=$(m68k-elf-gcc.exe -dumpversion)
echo "Target GCC version: $TARGET_GCC_VERSION"

# Get the plugin directory from target GCC
PLUGIN_DIR=$(m68k-elf-gcc.exe -print-file-name=plugin)
PLUGIN_INCLUDE="$PLUGIN_DIR/include"
echo "Plugin include from target GCC: $PLUGIN_INCLUDE"

# Host GCC paths
GCC_INC_MINGW64="/mingw64/include"
GCC_INC_PLUGIN_MINGW64="/mingw64/lib/gcc/x86_64-w64-mingw32/$HOST_GCC_VERSION/plugin/include"

echo "Building plugin for target GCC ..."

# Build the plugin
# Note: when you use gcc to call plugin, you should link plugin with libcc1.a, and if you use g++ to call plugin, 
# you should link plugin with libcc1plus.a. You can't mix linking, or you will get segment fault.
g++ -I"$PLUGIN_INCLUDE" -I"$GCC_INC_MINGW64" -I"$GCC_INC_PLUGIN_MINGW64" -DIN_GCC \
    -shared -fPIC -fno-rtti -fpermissive -Wno-pointer-arith -Wno-unused-result \
	-Wl,--export-all-symbols \
    optimizer_plugin.c -o optimizer_plugin.dll "$PLUGIN_DIR/cc1.exe.a"

if [ $? -eq 0 ]; then
    echo "Plugin built successfully: optimizer_plugin.dll"
else
    echo "Plugin build failed!"
    exit 1
fi