#!/bin/bash

# First convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_plugin_full_c.sh
# chmod +x build_plugin_full_c.sh
# ./build_plugin_full_c.sh

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

cython3 --3str optimize_lst_c_wrapper.pyx -o optimize_lst_c_wrapper.c
if [ $? -ne 0 ]; then
    echo "Failed to compile python script with cython3"
    exit 1
fi

cython3 --3str ../optimize_lst.py -o optimize_lst.c
if [ $? -ne 0 ]; then
    echo "Failed to compile python script with cython3"
    exit 1
fi

cython3 --3str ../optimize_mul_patterns.py -o optimize_mul_patterns.c
if [ $? -ne 0 ]; then
    echo "Failed to compile python script with cython3"
    exit 1
fi

# Try to find python executable
PYTHON_EXEC=$(which python3 2>/dev/null || which python 2>/dev/null)

if [ -z "$PYTHON_EXEC" ]; then
    echo "Error: Python not found" >&2
    exit 1
fi

# Python include path
# Eg: /usr/include/python3.12
PYTHON_INC=$($PYTHON_EXEC -c "import sysconfig; print(sysconfig.get_path('include'))")

# Get library name using python3-config
# Eg: libpyhton3.12.a or libpyhton3.12.so
PYTHON_LIB_NAME=$(python3-config --libs 2>/dev/null | grep -o '\-lpython[0-9.]*' | sed 's/-l//')

# Fallback if python3-config doesn't work
if [ -z "$PYTHON_LIB_NAME" ]; then
    PYTHON_VERSION=$($PYTHON_EXEC -c "import sys; vi=sys.version_info; print(f'{vi.major}.{vi.minor}')")
    PYTHON_LIB_NAME="python${PYTHON_VERSION}"
fi

# Get library directory
# Eg: /usr/lib/x86_64-linux-gnu
PYTHON_LIB_DIR=$($PYTHON_EXEC -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))" 2>/dev/null)

if [ -z "$PYTHON_LIB_DIR" ] || [ ! -d "$PYTHON_LIB_DIR" ]; then
    # Try python3-config for library directory
    PYTHON_LIB_DIR=$(python3-config --prefix 2>/dev/null)/lib
fi

echo "Python Include: -I$PYTHON_INC"
echo "Python Library: -L$PYTHON_LIB_DIR -l$PYTHON_LIB_NAME"

echo "Compiling python translated to c units ... THIS STEP TAKES MORE THAN 15 MINS DUE TO FLAG -O2"
g++ -I"$PYTHON_INC" \
	-fPIC -fno-rtti -fpermissive -Wno-pointer-arith -Wno-unused-result \
    -fwrapv -pthread -O2 -fno-strict-aliasing \
    -c optimizer_plugin_cython_wrapper.c optimize_lst_c_wrapper.c optimize_lst.c optimize_mul_patterns.c

echo "Compiling plugin c unit ..."
g++ -I"$PLUGIN_INCLUDE" -I"$GCC_INC" -DIN_GCC -I"$PYTHON_INC" \
	-fPIC -fno-rtti -fpermissive -Wno-pointer-arith -Wno-unused-result \
	-c optimizer_plugin_full_c.c

echo "Linking everything ..."
g++ -shared -fPIC -fno-rtti \
	optimizer_plugin_full_c.o optimizer_plugin_cython_wrapper.o optimize_lst_c_wrapper.o optimize_lst.o optimize_mul_patterns.o \
	-o optimizer_plugin.so \
	-lcc1 -L"$PYTHON_LIB_DIR" -l"$PYTHON_LIB_NAME"

rm -f optimize_lst_c_wrapper.h optimize_lst_c_wrapper.c optimize_lst.c optimize_mul_patterns.c 2>/dev/null
rm -f optimizer_plugin_full_c.o optimizer_plugin_cython_wrapper.o optimize_lst_c_wrapper.o optimize_lst.o optimize_mul_patterns.o 2>/dev/null

if [ $? -eq 0 ]; then
    echo "Plugin built successfully: optimizer_plugin.so"
else
    echo "Plugin build failed!"
    exit 1
fi