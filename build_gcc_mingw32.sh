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
# Copy the script build_gcc_mingw32.sh here

# Convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_gcc_mingw32.sh
# chmod +x build_gcc_mingw32.sh
# ./build_gcc_mingw32.sh

BASE_BUILD_DIR=$HOME
M68K_GCC_TOOLCHAIN=${BASE_BUILD_DIR}/m68k-elf-gcc-mingw32
# We need the gcc m68k toolchain for linux already built
M68K_GCC_TOOLCHAIN_LINUX=${BASE_BUILD_DIR}/m68k-elf-gcc

TARGET="m68k-elf"
TARGET_CPU="68000"
HOST="x86_64-w64-mingw32"

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
  sudo apt install -y build-essential gcc-13-plugin-dev libgmp-dev libmpc-dev libmpfr-dev \
                      make flex bison texinfo git wget mingw-w64 libltdl-dev
  if [ $? -ne 0 ]; then
    echo "Failed to install dependencies"
    exit 1
  fi
}

deps_check() {
  for i in "git" "make" "wget" "makeinfo" "x86_64-w64-mingw32-gcc" "x86_64-w64-mingw32-g++"
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

  export CC=/usr/bin/x86_64-w64-mingw32-gcc
  export CXX=/usr/bin/x86_64-w64-mingw32-g++
  export AR=/usr/bin/x86_64-w64-mingw32-ar
  export RANLIB=/usr/bin/x86_64-w64-mingw32-ranlib
  export LD=/usr/bin/x86_64-w64-mingw32-ld

  # Build binutils
  mkdir -p ${M68K_GCC_TOOLCHAIN}/build/${BINUTILS_DIR}
  cd ${M68K_GCC_TOOLCHAIN}/build/${BINUTILS_DIR}

  ${M68K_GCC_TOOLCHAIN}/src/${BINUTILS_DIR}/configure \
    --target=$TARGET \
    --host=$HOST \
    --prefix=$M68K_GCC_TOOLCHAIN \
    --with-cpu=$TARGET_CPU \
    --with-included-ltdl \
    --enable-plugins \
    --disable-nls \
    --disable-werror \
    --disable-multilib \
    --disable-manpages \
    --disable-info \
	--without-zstd \
    --without-headers \
    --without-newlib

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
    --enable-shared \
    --without-zstd \
    --without-headers \
    --without-newlib \
    --disable-libstdcxx \
    --disable-threads \
    --disable-libssp \
    --disable-libgomp \
    --disable-libquadmath \
    --disable-libmudflap \
    --disable-manpages \
    --disable-info \
    --disable-nls

  if [ $? -ne 0 ]; then
    echo "GCC configure failed"
    exit 1
  fi

  # Build only GCC first (not the full toolchain)
  echo "Building GCC compiler only..."
  make -j$CORE_COUNT V=1 all-gcc
  if [ $? -ne 0 ]; then
    echo "GCC build failed"
    exit 1
  fi

  # Now build libgcc
  echo "Building libgcc..."
  make -j$CORE_COUNT V=1 all-target-libgcc
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

copy_files_for_sgdk() {
  cd $BASE_BUILD_DIR
  TARGET_SGDK_FILES_PATH="sgdk_bin"
  
  # Create TARGET_SGDK_FILES_PATH folder if not exists already
  if [ ! -d "$TARGET_SGDK_FILES_PATH" ]; then
      mkdir -p "$TARGET_SGDK_FILES_PATH"
  else
      rm -rf "$TARGET_SGDK_FILES_PATH"/*
  fi
  
  echo "Copying required DLL files from MINGW to target folder..."
  
  MINGW_USR_LIB_PATH=/usr/lib/gcc/$HOST/13-win32
  MINGW_USR_PATH=/usr/$HOST/lib
  MINGW_DLL_LIST="libgcc_s_seh-1.dll libstdc++-6.dll libwinpthread-1.dll"

  for DLL in $MINGW_DLL_LIST; do
      if [ -f "$MINGW_USR_LIB_PATH/$DLL" ]; then
          echo "Copying $DLL"
          cp "$MINGW_USR_LIB_PATH/$DLL" "$TARGET_SGDK_FILES_PATH/"
      elif [ -f "$MINGW_USR_PATH/$DLL" ]; then
          echo "Copying $DLL"
          cp "$MINGW_USR_PATH/$DLL" "$TARGET_SGDK_FILES_PATH/"
      else
          echo "Error: $DLL not found in $MINGW_USR_LIB_PATH nor in $MINGW_USR_PATH"
      fi
  done
  
  echo "Done copying MINGW DLL files."
  
  echo "Copying GCC libs and exec files..."
  
  GCC_LIB_EXEC="$M68K_GCC_TOOLCHAIN/libexec/gcc/$TARGET/$GCC_VERSION"
  GCC_LIB_EXEC_LIST="cc1.exe liblto_plugin.dll liblto_plugin.dll.a lto1.exe lto-wrapper.exe"

  if [ ! -d "$GCC_LIB_EXEC" ]; then
      echo "Error: GCC libexec directory not found: $GCC_LIB_EXEC"
  fi
  
  for FILE in $GCC_LIB_EXEC_LIST; do
      if [ -f "$GCC_LIB_EXEC/$FILE" ]; then
          echo "Copying $FILE"
          cp "$GCC_LIB_EXEC/$FILE" "$TARGET_SGDK_FILES_PATH/"
      else
          echo "Error: $FILE not found in $GCC_LIB_EXEC"
      fi
  done

  echo "Done copying GCC libs and exec files."
  
  echo "Copy and rename all files in bin directory by removing the 'm68k-elf-' prefix"
  
  GCC_BINS="$M68K_GCC_TOOLCHAIN/bin"
  GCC_BINS_LIST="ar as cpp gcc gdb ld nm objcopy objdump size"

  if [ -d "$GCC_BINS" ]; then
      for FILE in $GCC_BINS_LIST; do
        if [ -f "$GCC_BINS/m68k-elf-$FILE.exe" ]; then
            echo "Copying m68k-elf-$FILE.exe"
            cp "$GCC_BINS/m68k-elf-$FILE.exe" "$TARGET_SGDK_FILES_PATH/"
        else
            echo "Error: m68k-elf-$FILE.exe not found in $GCC_BINS"
        fi
      done
	  # Rename m68k-elf-* files by removing the prefix
      cd "$TARGET_SGDK_FILES_PATH"
      for FILE in m68k-elf-*; do
          if [ -e "$FILE" ]; then
              newname="${FILE#m68k-elf-}"
              if [ "$newname" != "$FILE" ]; then
                  echo "Renaming '$FILE' to '$newname'"
                  mv "$FILE" "$newname"
              fi
          fi
      done
      cd $BASE_BUILD_DIR
  else
      echo "Error: GCC binaries directory not found at $GCC_BINS"
  fi

  echo "Done."
}

# Check for existence of gcc m68k toolchain for Linux
if [ ! -d "${M68K_GCC_TOOLCHAIN_LINUX}" ] || [ ! -d "${M68K_GCC_TOOLCHAIN_LINUX}/bin" ]; then
    echo "Error: Required toolchain directories are missing"
    echo "Please ensure both directories exist:"
    echo "  - ${M68K_GCC_TOOLCHAIN_LINUX}"
    echo "  - ${M68K_GCC_TOOLCHAIN_LINUX}/bin"
    exit 1
fi

# We need the gcc m68k toolchain for linux already built and in the PATH
export PATH=${M68K_GCC_TOOLCHAIN_LINUX}/bin:$PATH

# Main execution
echo "Starting m68k-elf Windows toolchain build for SGDK with plugin support..."
install_deps
deps_check
clean_build
download_and_unzip
build_toolchain
copy_files_for_sgdk

echo ""
echo "---------------------------------------------------------"
echo "Windows Toolchain with plugin support built successfully!"
echo "---------------------------------------------------------"

export PATH=${M68K_GCC_TOOLCHAIN}/bin:$PATH
m68k-elf-gcc.exe --version
m68k-elf-as.exe --version
m68k-elf-gdb.exe --version
echo ""
echo "Check if plugins are supported in the linker"
m68k-elf-ld.exe --help | grep -i plugin
echo ""
echo "Check GCC plugin support (output must be different than 'plugin')"
m68k-elf-gcc.exe -print-file-name=plugin
echo "(If it's 'plugin' then use path: $M68K_GCC_TOOLCHAIN/lib/gcc/$TARGET/$GCC_VERSION/plugin)"