#!/bin/bash

# First convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_plugin_full_c.sh
# chmod +x build_plugin_full_c.sh
# ./build_plugin_full_c.sh

clean_files() {
	rm -f optimize_lst_c_wrapper.h optimize_lst_c_wrapper.c optimize_lst.c optimize_mul_patterns.c 2>/dev/null
	rm -f optimizer_plugin_cython_wrapper.o optimize_lst_c_wrapper.o optimize_lst.o optimize_mul_patterns.o 2>/dev/null
	rm -f optimizer_plugin_full_c.o  2>/dev/null
}

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

# Python include path
# This path is created by the script that builds the python static lib
PYTHON_STATIC_LIB_INC="/opt/python3.10-static/include/python3.10"

# This lib is created by the script that builds the python static lib
PYTHON_STATIC_LIB_NAME="libpython3.10.a"

# This path is created by the script that builds the python static lib
PYTHON_STATIC_LIB_DIR="/opt/python3.10-static/lib"

# This path is created by the script that builds the python static lib
OPENSSL_STATIC_LIB_DIR="/opt/openssl-1.1.1-static/lib"

echo "Python static Include: -I$PYTHON_STATIC_LIB_INC"
echo "Python static Library: -L$PYTHON_STATIC_LIB_DIR -l:$PYTHON_STATIC_LIB_NAME"
echo "OpenSSL 1.1.1 static Library: -L$OPENSSL_STATIC_LIB_DIR"

cython3 --3str optimize_lst_c_wrapper.pyx -o optimize_lst_c_wrapper.c
if [ $? -ne 0 ]; then
    echo "Failed to compile python script with cython3"
	clean_files
    exit 1
fi

cython3 --3str optimize_lst.py -o optimize_lst.c
if [ $? -ne 0 ]; then
    echo "Failed to compile python script with cython3"
	clean_files
    exit 1
fi

cython3 --3str optimize_mul_patterns.py -o optimize_mul_patterns.c
if [ $? -ne 0 ]; then
    echo "Failed to compile python script with cython3"
	clean_files
    exit 1
fi

echo "Compiling python translated to c units and final executable ... THIS STEP TAKES MORE THAN 15 MINS DUE TO FLAG -O2"
g++ -static -no-pie -static-libgcc -static-libstdc++ \
	-I"$PYTHON_STATIC_LIB_INC" \
    -fno-rtti -fpermissive -Wno-pointer-arith -Wno-unused-result \
	-fwrapv -pthread -fno-strict-aliasing \
	optimizer_plugin_cython_wrapper.c optimize_lst_c_wrapper.c optimize_lst.c optimize_mul_patterns.c \
	-o optimize_lst_exe \
	-L"$PYTHON_STATIC_LIB_DIR" -l:"$PYTHON_STATIC_LIB_NAME" \
	-L"$OPENSSL_STATIC_LIB_DIR" \
	-lcrypto -lssl -lz -lbz2 -lffi -lsqlite3 -llzma -ldl -lpthread -lm
#	-cc1plus
if [ $? -ne 0 ]; then
    echo "Failed to compile python into c files and final executable"
	clean_files
    exit 1
fi
chmod +x optimize_lst_exe

echo "Compiling plugin c unit ..."
g++ -shared -I"$PLUGIN_INCLUDE" -I"$GCC_INC" -DIN_GCC \
    -fPIC -fno-rtti -fpermissive -Wno-pointer-arith -Wno-unused-result \
    optimizer_plugin_full_c.c -o optimizer_plugin.so -lcc1
if [ $? -ne 0 ]; then
    echo "Failed to compile plugin c unit"
	clean_files
    exit 1
fi

clean_files
echo "Plugin built successfully: optimizer_plugin.so"
