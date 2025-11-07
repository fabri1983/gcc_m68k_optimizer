#!/bin/bash

# First convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_plugin.sh
# chmod +x build_plugin.sh
# ./build_plugin.sh

HOST_GCC_VERSION=$(gcc -dumpversion)
echo "Host GCC version: $HOST_GCC_VERSION"
TARGET_GCC_VERSION=$(m68k-elf-gcc -dumpversion)
echo "Target GCC version: $TARGET_GCC_VERSION"

# Get the plugin directory from target GCC
PLUGIN_DIR=$(m68k-elf-gcc -print-file-name=plugin)
PLUGIN_INCLUDE="$PLUGIN_DIR/include"
echo "Plugin include from target GCC: $PLUGIN_INCLUDE"

# Host GCC paths
GCC_INC="/usr/include"

echo "Building plugin for target GCC ..."

# Build the plugin
# Note: when you use gcc to call plugin, you should link plugin with libcc1.a, and if you use g++ to call plugin, 
# you should link plugin with libcc1plus.a. You can't mix linking, or you will get segment fault.
g++ -I"$PLUGIN_INCLUDE" -I"$GCC_INC" -DIN_GCC \
    -shared -fPIC -fno-rtti -fpermissive -Wno-pointer-arith -Wno-unused-result \
    optimizer_plugin.c -o optimizer_plugin.so -lcc1

if [ $? -eq 0 ]; then
    echo "Plugin built successfully: optimizer_plugin.so"
else
    echo "Plugin build failed!"
    exit 1
fi