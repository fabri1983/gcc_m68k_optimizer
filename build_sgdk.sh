#!/bin/bash

# Convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_sgdk.sh
# chmod +x build_sgdk.sh
# ./build_sgdk.sh

BASE_BUILD_DIR=$HOME
M68K_GCC_TOOLCHAIN=${BASE_BUILD_DIR}/m68k-elf-gcc

GDK=${BASE_BUILD_DIR}/SGDK
GDK_VERSION="master"
#GDK_VERSION="v2.11" # use this for tagged releases

SJASM_SRC=${GDK}/Sjasm/Sjasm
SJASM_VERSION="v0.39" # for some reason this version works for x86 linux

CORE_COUNT=$(nproc)

# deps: (there might be something missing here)
# libmpc texinfo git make java makeinfo

install_deps() {
  echo "Installing dependencies..."
  sudo apt install -y openjdk-17-jre
}

deps_check() {
  for i in "git" "make" "java" "makeinfo"
  do
    if [ "$(which $i)" == "" ]
    then
      echo "$i is not installed"
      if [ "$i" == "java" ]
      then
        echo "install openjdk-17-jre"
      elif [ "$i" == "makeinfo" ]
      then
        echo "install texinfo"
      fi
      exit
    fi
  done
  if [ ! -d $M68K_GCC_TOOLCHAIN ]
  then
    echo ""
    echo "gcc toolchain not installed? build toolchain first."
    echo ""
    exit
  fi
  if [ ! -f ${M68K_GCC_TOOLCHAIN}/bin/m68k-elf-gcc ]
  then
    echo ""
    echo "gcc toolchain not installed? build toolchain first."
    echo ""
    exit
  fi
}

clean_build() {
  if [ ! -d $BASE_BUILD_DIR ]
  then
    mkdir $BASE_BUILD_DIR
  fi

  if [ -d $GDK ]
  then
    rm -rf $GDK
  fi

  cd $BASE_BUILD_DIR
  git clone https://github.com/Stephane-D/SGDK.git --depth=1
  cd $GDK
  git checkout $GDK_VERSION
  git clone https://github.com/Konamiman/Sjasm
  cd Sjasm
  git checkout $SJASM_VERSION
  cd $GDK
}

build_sjasm() {
  cd $SJASM_SRC
  make clean

#  export CXX=/usr/bin/g++
#  export CC=/usr/bin/gcc

  make sjasm -j$CORE_COUNT
  if [ ! -f sjasm ]
  then
    echo "sjasm build failed?"
    exit
  fi
  cp sjasm ${GDK}/bin/sjasm
}

build_sgdktools() {
  cd $GDK/tools/xgmtool
  gcc src/*.c -Wall -O2 -lm -o xgmtool
  strip xgmtool
  cp xgmtool ${GDK}/bin/
  cd $GDK/tools/bintos
  gcc src/bintos.c -Wall -O2 -o bintos
  strip bintos
  cp bintos ${GDK}/bin/
  cd ${GDK}/tools/convsym
  make -j$CORE_COUNT
  cp build/convsym ${GDK}/bin/
}

install_deps
deps_check
clean_build
build_sjasm
PATH=${GDK}/bin:$PATH
build_sgdktools
PATH=${M68K_GCC_TOOLCHAIN}/bin:$PATH
#cd $GDK
#make -f makelib.gen clean-release
#make -f makelib.gen release
#make -f makelib.gen clean-debug
#make -f makelib.gen debug

echo ""
echo "----------------------------------------------------"
echo "Set GDK env:"
echo "export GDK=${GDK}"
echo ""
echo "Add SGDK bin tools to PATH:"
echo "export PATH=${GDK}/bin:\$PATH"
echo ""
echo "Build manually SGDK libs libmd.a and libmd_debug.a with:"
echo "cd \$GDK"
echo "make -f makelib.gen clean-release"
echo "make -f makelib.gen release"
echo "make -f makelib.gen clean-debug"
echo "make -f makelib.gen debug"
echo ""
echo "Build project with:"
echo "Edit makefile.gen and add next line after the inclusion of common.mk:"
echo "PLUGIN_PARAM := -fplugin=\$(GDK)/tools/optimizer_plugin.so -fplugin-arg-optimizer_plugin-disable=0 -fplugin-arg-optimizer_plugin-keep-files=0"
echo "Add \$(PLUGIN_PARAM) to the target: \$(OUT_DIR)/rom.out: \$(OUT_DIR)/sega.o \$(OUT_DIR)/cmd_ \$(LIBMD)"
echo "make -f ${GDK}/makefile.gen release -j1"
echo ""
