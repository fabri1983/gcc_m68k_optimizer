#!/usr/bin/bash
set -euo pipefail

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
# Copy the script build_gcc_mint_15.2.0.sh here

# Convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_gcc_mint_15.2.0.sh
# Set execution permissions
#   chmod +x build_gcc_mint_15.2.0.sh
#   ./build_gcc_mint_15.2.0.sh

BASE_BUILD_DIR=$HOME
M68K_GCC_TOOLCHAIN=${BASE_BUILD_DIR}/m68k-elf-gcc-mint

TARGET="m68k-elf"
TARGET_CPU="68000"
HOST="x86_64-linux-gnu"
BUILD="x86_64-linux-gnu"

GCC_MIRROR="https://mirrors.ocf.berkeley.edu/gnu"

GCC_VERSION="15.2.0"
GCC_DIR_NAME="m68k-atari-mint-gcc-${GCC_VERSION}-experimental-v2"

BINUTILS_VERSION="2.45"
BINUTILS_DIR="binutils-${BINUTILS_VERSION}"
BINUTILS_FILE="${BINUTILS_DIR}.tar.gz"
BINUTILS_URL="${GCC_MIRROR}/binutils/$BINUTILS_FILE"

GDB_VERSION="16.3"
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
  mkdir -p "$(dirname "$GCC_DIR_NAME")"
  git clone -b mint/gcc-15-experimental-v2 https://github.com/th-otto/m68k-atari-mint-gcc.git $GCC_DIR_NAME
  if [ $? -ne 0 ]; then
    echo "Failed to download GCC from github"
    exit 1
  fi

  echo "Create compilation rules for the experimental m68k backend objects..."
  cat > "$GCC_DIR_NAME/gcc/config/m68k/t-m68k-experimental-backend" <<'EOF'
# M68K backend implementation objects.

m68k_costs.o: $(srcdir)/config/m68k/m68k_costs.cc
	$(COMPILE) $<
	$(POSTCOMPILE)

m68k-util.o: $(srcdir)/config/m68k/m68k-util.cc $(srcdir)/config/m68k/m68k-util.h
	$(COMPILE) $<
	$(POSTCOMPILE)

m68k-pass-regalloc.o: $(srcdir)/config/m68k/m68k-pass-regalloc.cc
	$(COMPILE) $<
	$(POSTCOMPILE)

m68k-doloop.o: $(srcdir)/config/m68k/m68k-doloop.cc
	$(COMPILE) $<
	$(POSTCOMPILE)

m68k-pass-memreorder.o: $(srcdir)/config/m68k/m68k-pass-memreorder.cc
	$(COMPILE) $<
	$(POSTCOMPILE)

m68k-pass-autoinc.o: $(srcdir)/config/m68k/m68k-pass-autoinc.cc
	$(COMPILE) $<
	$(POSTCOMPILE)

m68k-pass-shortopt.o: $(srcdir)/config/m68k/m68k-pass-shortopt.cc
	$(COMPILE) $<
	$(POSTCOMPILE)

m68k-pass-miscopt.o: $(srcdir)/config/m68k/m68k-pass-miscopt.cc
	$(COMPILE) $<
	$(POSTCOMPILE)

PASSES_EXTRA += $(srcdir)/config/m68k/m68k-passes.def
EOF
  if [ $? -ne 0 ]; then
    echo "Failed to create compilation rules"
    exit 1
  fi

  echo "Applying m68k elf backend object-list fix into config GCC..."
  git -C "$GCC_DIR_NAME" apply - <<'PATCH'
diff --git a/gcc/config.gcc b/gcc/config.gcc
--- a/gcc/config.gcc
+++ b/gcc/config.gcc
@@ -2391,5 +2391,6 @@ m68k-*-elf* | fido-*-elf*)
 	*)
 		default_m68k_cpu=68000
 		default_cf_cpu=5206
+		extra_objs="${extra_objs} m68k_costs.o m68k-util.o m68k-pass-regalloc.o m68k-pass-memreorder.o m68k-pass-autoinc.o m68k-pass-shortopt.o m68k-pass-miscopt.o m68k-doloop.o"
 		;;
 	esac
@@ -2400,7 +2401,7 @@ m68k-*-elf* | fido-*-elf*)
 	case ${target} in
 	fido-*-elf*)
 		;;
 	*)
-		tmake_file="$tmake_file m68k/t-mlibs"
+		tmake_file="$tmake_file m68k/t-mlibs m68k/t-m68k-experimental-backend"
 		;;
 	esac
PATCH
  if [ $? -ne 0 ]; then
    echo "Failed to apply config patch into GCC"
    exit 1
  fi

  cd $GCC_DIR_NAME
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
	--build=$BUILD \
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
#    --build=$BUILD \
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
  mkdir -p ${M68K_GCC_TOOLCHAIN}/build/${GCC_DIR_NAME}
  cd ${M68K_GCC_TOOLCHAIN}/build/${GCC_DIR_NAME}

  ${M68K_GCC_TOOLCHAIN}/src/${GCC_DIR_NAME}/configure \
    --target=$TARGET \
    --host=$HOST \
    --build=$BUILD \
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
echo "  export PATH=${M68K_GCC_TOOLCHAIN}/bin:\$PATH"
echo "----------------------------------------------------"

export PATH=${M68K_GCC_TOOLCHAIN}/bin:$PATH
m68k-elf-gcc --version
m68k-elf-as --version
#m68k-elf-gdb --version
echo ""
echo "Check if plugins are supported in the linker"
m68k-elf-ld --help | grep -i plugin
echo ""
echo "Check GCC plugin support (output must be different than 'plugin')"
m68k-elf-gcc -print-file-name=plugin