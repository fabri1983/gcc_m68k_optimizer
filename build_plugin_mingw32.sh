#!/bin/bash

# First convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_plugin_mingw32.sh
# chmod +x build_plugin_mingw32.sh
# ./build_plugin_mingw32.sh

HOST_GCC_VERSION=$(x86_64-w64-mingw32-gcc -dumpversion)
echo "Host GCC version: $HOST_GCC_VERSION"
TARGET_GCC_VERSION=$(m68k-elf-gcc.exe -dumpversion)
echo "Target GCC version: $TARGET_GCC_VERSION"

# Get the plugin directory from target GCC
PLUGIN_DIR=$(m68k-elf-gcc.exe -print-file-name=plugin)
PLUGIN_INCLUDE="$PLUGIN_DIR/include"
echo "Plugin include target GCC: $PLUGIN_INCLUDE"

# Host GCC paths
GCC_INC="/usr/include"

echo "Building plugin for target GCC ..."

# Build the plugin
# Note: when you use gcc to call plugin, you should link plugin with libcc1.a, and if you use g++ to call plugin, 
# you should link plugin with libcc1plus.a. You can't mix linking, or you will get segment fault.
x86_64-w64-mingw32-g++ -I"$PLUGIN_INCLUDE" -I"$GCC_INC" -DIN_GCC \
    -shared -fPIC -fno-rtti -fpermissive -Wno-pointer-arith -Wno-unused-result \
	-Wl,--export-all-symbols \
    optimizer_plugin.c -o optimizer_plugin.so cc1.exe.a

if [ $? -eq 0 ]; then
    echo "Plugin built successfully: optimizer_plugin.dll"
else
    echo "Plugin build failed!"
    exit 1
fi