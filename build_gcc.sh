#!/usr/bin/bash

# Run this script in WSL with Ubuntu distro.
# First install WSL for Windows. By default it will come with Ubuntu distro, but if not then:
#   wsl --list
# if Ubuntu distro then:
#   wsl --install
# Then set user and pass:
#   Create a default Unix user account: <user_name>
#   pass: <your pass>
# Then you can launh it by opening a console windows and type:
#   wsl -d Ubuntu
# Initial location is to /mnt/c/Users/<user_name>
# So move to $HOME
#   cd $HOME
# Open a Explorer windows and locate into \\wsl.localhost\Ubuntu\home\<user_name>
# Copy the script build_gcc.sh here

# Convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_gcc.sh
# chmod +x build_gcc.sh
# ./build_gcc.sh

BASE_BUILD_DIR=$HOME
M68K_GCC_TOOLCHAIN=${BASE_BUILD_DIR}/m68k-elf-gcc

TARGET="m68k-elf"
TARGET_CPU="68000"
HOST="x86_64-linux-gnu"

GCC_MIRROR="https://mirrors.ocf.berkeley.edu/gnu"

GCC_VERSION="13.2.0"
GCC_DIR="gcc-${GCC_VERSION}"
GCC_FILE="${GCC_DIR}.tar.gz"
GCC_URL="${GCC_MIRROR}/gcc/${GCC_DIR}/$GCC_FILE"

BINUTILS_VERSION="2.44"
BINUTILS_DIR="binutils-${BINUTILS_VERSION}"
BINUTILS_FILE="${BINUTILS_DIR}.tar.gz"
BINUTILS_URL="${GCC_MIRROR}/binutils/$BINUTILS_FILE"

GDB_VERSION="14.2"
GDB_DIR="gdb-${GDB_VERSION}"
GDB_FILE="${GDB_DIR}.tar.gz"
GDB_URL="${GCC_MIRROR}/gdb/$GDB_FILE"

CORE_COUNT=$(nproc)

# Install dependencies in WSL
install_deps() {
  echo "Installing dependencies..."
  sudo apt update
  sudo apt install -y build-essential libgmp-dev libmpc-dev libmpfr-dev \
                      make flex bison texinfo git wget gcc-13-plugin-dev gcc-13 g++-13
                      # pkg-config libzstd-dev zlib1g-dev
  if [ $? -ne 0 ]; then
    echo "Failed to install dependencies"
    exit 1
  fi
}

deps_check() {
  for i in "git" "make" "wget" "makeinfo" "gcc" "g++"
  do
    if [ "$(which $i 2>/dev/null)" == "" ]
    then
      echo "$i is not installed"
      exit 1
    fi
  done
}

clean_build() {
  if [ ! -d $BASE_BUILD_DIR ]
  then
    mkdir -p $BASE_BUILD_DIR
  fi
  if [ -d $M68K_GCC_TOOLCHAIN ]
  then
    echo "Removing existing toolchain directory..."
    rm -rf $M68K_GCC_TOOLCHAIN
  fi
}

download_and_unzip() {
  cd $BASE_BUILD_DIR
  mkdir -p ${M68K_GCC_TOOLCHAIN}/src
  cd ${M68K_GCC_TOOLCHAIN}/src

  echo "Downloading binutils..."
  wget $BINUTILS_URL
  if [ $? -ne 0 ]; then
    echo "Failed to download binutils"
    exit 1
  fi

  echo "Extracting binutils..."
  tar -xzf $BINUTILS_FILE
  rm $BINUTILS_FILE

  echo "Downloading GDB..."
  wget $GDB_URL
  if [ $? -ne 0 ]; then
    echo "Failed to download GDB"
    exit 1
  fi

  echo "Extracting GDB..."
  tar -xzf $GDB_FILE
  rm $GDB_FILE

  echo "Downloading GCC..."
  wget $GCC_URL
  if [ $? -ne 0 ]; then
    echo "Failed to download GCC"
    exit 1
  fi

  echo "Extracting GCC..."
  tar -xzf $GCC_FILE
  rm $GCC_FILE

  cd ${GCC_DIR}
  echo "Downloading GCC prerequisites..."
  ./contrib/download_prerequisites
  if [ $? -ne 0 ]; then
    echo "Failed to download GCC prerequisites"
    exit 1
  fi
}

build_toolchain() {
  cd $BASE_BUILD_DIR
  mkdir -p ${M68K_GCC_TOOLCHAIN}/build

  export PATH=$M68K_GCC_TOOLCHAIN/bin:$PATH

  # Build binutils with plugins support
  mkdir -p ${M68K_GCC_TOOLCHAIN}/build/${BINUTILS_DIR}
  cd ${M68K_GCC_TOOLCHAIN}/build/${BINUTILS_DIR}

  ${M68K_GCC_TOOLCHAIN}/src/${BINUTILS_DIR}/configure \
    --target=$TARGET \
	--host=$HOST \
    --prefix=$M68K_GCC_TOOLCHAIN \
    --with-cpu=$TARGET_CPU \
    --enable-plugins \
    --disable-nls \
    --disable-werror \
    --disable-multilib \
    --disable-manpages \
    --disable-info \
    --without-headers \
    --without-newlib
#    --with-zstd \
#    --with-zlib

  if [ $? -ne 0 ]; then
    echo "Binutils configure failed"
    exit 1
  fi
  
  make -j$CORE_COUNT
  if [ $? -ne 0 ]; then
    echo "Binutils build failed"
    exit 1
  fi
  
  make install
  if [ $? -ne 0 ]; then
    echo "Binutils install failed"
    exit 1
  fi

  # Build gdb
#  mkdir -p ${M68K_GCC_TOOLCHAIN}/build/${GDB_DIR}
#  cd ${M68K_GCC_TOOLCHAIN}/build/${GDB_DIR}
#
#  ${M68K_GCC_TOOLCHAIN}/src/${GDB_DIR}/configure \
#    --target=$TARGET \
#    --host=$HOST \
#    --prefix=$M68K_GCC_TOOLCHAIN \
#    --with-cpu=$TARGET_CPU \
#    --disable-nls \
#    --disable-werror \
#    --with-expat \
#    --with-lzma \
#    --with-zlib \
#    --with-python=no \
#    --without-babeltrace \
#    --without-guile \
#    --without-libunwind-ia64 \
#    --disable-sim \
#    --disable-source-highlight \
#    --disable-manpages \
#    --disable-info \
#
#  if [ $? -ne 0 ]; then
#    echo "GDB configure failed"
#    exit 1
#  fi
#
#  make -j$CORE_COUNT
#  if [ $? -ne 0 ]; then
#    echo "GDB build failed"
#    exit 1
#  fi
#
#  make install
#  if [ $? -ne 0 ]; then
#    echo "GDB install failed"
#    exit 1
#  fi

  # Build GCC with plugin support
  mkdir -p ${M68K_GCC_TOOLCHAIN}/build/${GCC_DIR}
  cd ${M68K_GCC_TOOLCHAIN}/build/${GCC_DIR}

  ${M68K_GCC_TOOLCHAIN}/src/${GCC_DIR}/configure \
    --target=$TARGET \
    --host=$HOST \
    --prefix=$M68K_GCC_TOOLCHAIN \
    --with-cpu=$TARGET_CPU \
    --enable-languages="c,c++" \
    --enable-plugin \
    --without-headers \
    --without-newlib \
    --disable-shared \
    --disable-libstdcxx \
    --disable-threads \
    --disable-libssp \
    --disable-libgomp \
    --disable-libquadmath \
    --disable-libmudflap \
    --disable-manpages \
    --disable-info \
    --disable-nls
#    --with-zstd \
#    --with-zlib

  if [ $? -ne 0 ]; then
    echo "GCC configure failed"
    exit 1
  fi

  # Build only GCC first (not the full toolchain)
  echo "Building GCC compiler only..."
  make -j$CORE_COUNT all-gcc
  if [ $? -ne 0 ]; then
    echo "GCC build failed"
    exit 1
  fi

  # Now build libgcc
  echo "Building libgcc..."
  make -j$CORE_COUNT all-target-libgcc
  if [ $? -ne 0 ]; then
    echo "libgcc build failed"
    exit 1
  fi

  echo "Installing GCC..."
  make install-gcc

  echo "Installing libgcc..."
  make install-target-libgcc

  # Clean up
  echo "Cleaning up build directories..."
  cd ${M68K_GCC_TOOLCHAIN}
  rm -rf build
  rm -rf src
  
  # Strip binaries (optional, for space savings)
  echo "Stripping binaries..."
  find $M68K_GCC_TOOLCHAIN -type f -executable -exec strip --strip-unneeded {} + 2>/dev/null || true
  find $M68K_GCC_TOOLCHAIN -name '*.a' -exec strip -g {} + 2>/dev/null || true
}

# Main execution
echo "Starting m68k-elf toolchain build for SGDK with plugin support..."
install_deps
deps_check
clean_build
download_and_unzip
build_toolchain

echo ""
echo "----------------------------------------------------"
echo "Toolchain with plugin support built successfully!"
echo "Add to your PATH: ${M68K_GCC_TOOLCHAIN}/bin"
echo "export PATH=${M68K_GCC_TOOLCHAIN}/bin:\$PATH"
echo "----------------------------------------------------"

export PATH=${M68K_GCC_TOOLCHAIN}/bin:$PATH
m68k-elf-gcc --version
m68k-elf-as --version
m68k-elf-gdb --version
echo ""
echo "Check if plugins are supported in the linker"
m68k-elf-ld --help | grep -i plugin
echo ""
echo "Check GCC plugin support (output must be different than 'plugin')"
m68k-elf-gcc -print-file-name=plugin