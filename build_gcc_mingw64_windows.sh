#!/usr/bin/bash

# Copyright (c) 2014-2024, A.Haarer, All rights reserved. LGPLv3.
# Modified by fabri1983 to add plugin support.

# Please use the MSYS2 MinGW64 shell, not the UCRT shell nor the MSYS.
# You can check which shell are you at by typing: 
#   echo $MSYSTEM
# Set execution permission (if needed):
#   chmod +x build_gcc_mingw64_windows.sh
#   ./build_gcc_mingw64_windows.sh

# Check if running in MINGW64 environment
if [[ "$MSYSTEM" != "MINGW64" ]]; then
    echo "Error: This script must be run in MINGW64 shell."
    echo "Current MSYSTEM is: $MSYSTEM"
    echo "Please use the MSYS2 MinGW64 shell (not UCRT64, CLANG64, or MSYS)."
    exit 1
fi

# Update package database and core system:
pacman -Syu --noconfirm
pacman -Su
# Install dependencies:
pacman -S --needed --noconfirm git msys2-runtime unzip make tar flex bison diffutils texinfo patch \
                               mingw-w64-x86_64-gcc mingw-w64-x86_64-libmangle-git mingw-w64-x86_64-make \
                               mingw-w64-x86_64-pkg-config mingw-w64-x86_64-tools-git mingw-w64-x86_64-winstorecompat-git \
                               libexpat-devel
#                               ncurses-devel

# Check if gcc is located at /mingw64/bin/gcc
GCC_PATH=$(which gcc)
if [[ "$GCC_PATH" != "/mingw64/bin/gcc" ]]; then
    echo "Error: gcc is not located at /mingw64/bin/gcc"
    echo "Current gcc path is: $GCC_PATH"
    echo "Try closing and then re open this terminal."
    exit 1
fi

# Operating system to build for
HOSTOS="windows"

# Target architecture
TARGETARCHITECTURE="m68k-elf"

# Execute an specific action: purge, download, build_gdb, package, sgdk_files
# Otherwise leave it empty
ACTION=$1

# Define package versions
BINUTILS="binutils-2.42"
GCCVER="gcc-13.2.0"
GCCVER_ONLY="13.2.0"
GDBVER="gdb-14.2"
MPFRVER="mpfr-4.2.1"
GMPVER="gmp-6.3.0"
MPCVER="mpc-1.3.1"
ISLVER="isl-0.26"

# Nmber of parallel make's jobs
MAKEJOBS=$(nproc)

# ----------------------------------- globals ------------------------------------

ROOTDIR=`pwd`
LOGFILE="$ROOTDIR/buildlog.txt"
HOSTINSTALLPATH="$ROOTDIR/toolchain-$TARGETARCHITECTURE-gcc"
PREREQPATH="$ROOTDIR/toolchain-prerequisites"

if [ ! -d $HOSTINSTALLPATH ]; then
    mkdir -p $HOSTINSTALLPATH
fi
  
export PATH=$HOSTINSTALLPATH/bin:$PATH

# --------------------------------- functions ------------------------------------

NOCOLOR='\033[0m'
RED='\033[0;31m'
GREEN='\033[0;32m'

function log_msg () {
	local logline="`date` $1"
	echo -e "${GREEN}$logline${NOCOLOR}" >> $LOGFILE
	echo -e "${GREEN}$logline${NOCOLOR}"
}

function log_err () {
	local logline="`date` $1"
	echo -e "${RED}$logline${NOCOLOR}" >> $LOGFILE
	echo -e "${RED}$logline${NOCOLOR}"
}

function prepare_source () {
    local BASEURL=$1
    local SOURCENAME=$2
    local ARCHTYPE=$3

    pushd $ROOTDIR/toolchain-cross-build > /dev/null

    if [ "$ARCHTYPE" = "git" ]; then
        if [ ! -f $SOURCENAME.$ARCHTYPE ]; then
            log_msg " cloning $BASEURL"
            git clone $BASEURL
        else
            log_msg " pulling update from $BASEURL"
            cd $SOURCENAME
            git pull
        fi
    else
        if [ ! -f $ROOTDIR/src-archives/$SOURCENAME.$ARCHTYPE ]; then
            log_msg " downloading $SOURCENAME"
            pushd $ROOTDIR/src-archives > /dev/null
            wget $BASEURL/$SOURCENAME.$ARCHTYPE
            popd > /dev/null
            log_msg " downloading $SOURCENAME finished"
        else
            log_msg " downloading $SOURCENAME skipped"
        fi
    fi

    if [ ! -d $SOURCENAME ]; then
        log_msg " unpacking $SOURCENAME"
        if [ "$ARCHTYPE" == "tar.bz2" ]; then
            tar -xjf ../src-archives/$SOURCENAME.$ARCHTYPE
        elif [ "$ARCHTYPE" = "tar.gz" ]; then
            tar -xzf ../src-archives/$SOURCENAME.$ARCHTYPE
        elif [ "$ARCHTYPE" = "tar.xz" ]; then
            tar -xJf ../src-archives/$SOURCENAME.$ARCHTYPE
        elif [ "$ARCHTYPE" = "zip" ]; then
            unzip ../src-archives/$SOURCENAME.$ARCHTYPE
        elif [ "$ARCHTYPE" = "git" ]; then
            echo "" # nothing to do for git
        else
            log_err " !!!!! unknown archive format"
            exit 1
        fi
        log_msg " unpacking $SOURCENAME finished"
    else
        log_msg " unpacking $SOURCENAME skipped"
    fi
    cd $SOURCENAME

    if [ ! -d cross-chain-$TARGETARCHITECTURE-obj ]; then
        mkdir cross-chain-$TARGETARCHITECTURE-obj
    fi

    popd > /dev/null

}

function conf_compile_source () {
    local SOURCEPACKAGE=$1
    local DETECTFILE=$2
    local CONFIGURESTRING=$3

    [ ! -d $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj ] && mkdir $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj

    pushd $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj > /dev/null

    log_msg "COMPILE sourcepackage= $SOURCEPACKAGE"
    log_msg "COMPILE detect file= $DETECTFILE"

    if [ ! -f config.status ]; then
        log_msg "configuring $SOURCEPACKAGE"
        ../configure $CONFIGURESTRING 2>&1 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-conf.log || exit 1
        log_msg "configuring $SOURCEPACKAGE finished"
    else
        log_msg "configuring $SOURCEPACKAGE skipped"
    fi
    
    if [ ! -f $DETECTFILE ]; then

        log_msg "building $SOURCEPACKAGE"
        make -j $MAKEJOBS 2>&1 V=2 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-build.log || exit 1
        if [ $? -eq 0 ]; then
            log_msg "building $SOURCEPACKAGE finished"
        else
            log_err "building $SOURCEPACKAGE failed"
        fi

        log_msg "install $SOURCEPACKAGE"
        install_package
        log_msg "install $SOURCEPACKAGE finished"
    else
        log_msg "compiling and install $SOURCEPACKAGE skipped"
    fi
    popd > /dev/null
}

# Function to install a single package
function install_package () {
    make install 2>&1 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-install.log
    if [ $? -eq 0 ]; then
        log_msg "install finished"
    else
        log_err "install failed"
    fi
}

# Remove all intermediate products of a single package
function purge_pkg () {
    local PACKAGE=$1
    [ -d $ROOTDIR/toolchain-cross-build/$PACKAGE ] && rm -rf $ROOTDIR/toolchain-cross-build/$PACKAGE
	[ -d $PREREQPATH/$PACKAGE ] && rm -rf $PREREQPATH/$PACKAGE
}

function download_all_pkg () {
    [ ! -d $ROOTDIR/toolchain-cross-build ] && mkdir $ROOTDIR/toolchain-cross-build
    [ ! -d $ROOTDIR/src-archives ] && mkdir $ROOTDIR/src-archives

    #prepare_source http://ftp.gnu.org/gnu/binutils $BINUTILS tar.bz2
    prepare_source https://mirrors.ocf.berkeley.edu/gnu/binutils $BINUTILS tar.bz2

    #prepare_source ftp://ftp.gwdg.de/pub/misc/gcc/releases/$GCCVER $GCCVER tar.xz
    prepare_source https://mirrors.ocf.berkeley.edu/gnu/gcc/$GCCVER $GCCVER tar.xz

    #prepare_source http://ftp.gnu.org/gnu/gdb $GDBVER tar.xz
    prepare_source https://mirrors.ocf.berkeley.edu/gnu/gdb $GDBVER tar.xz

    prepare_source https://gmplib.org/download/gmp $GMPVER tar.xz 

    prepare_source https://www.mpfr.org/$MPFRVER $MPFRVER tar.xz

    prepare_source https://www.multiprecision.org/downloads $MPCVER tar.gz

    prepare_source https://libisl.sourceforge.io $ISLVER tar.bz2
}

# --------------------------------------------------------------------------------

# Build pio package
function make_pio_package () {

    # Works only in bash
    PACKAGEVER=${GCCVER/#gcc-}

	echo "on windows, copy msys2 dlls"
	for DLLFILE in msys-gcc_s-seh-1.dll msys-2.0.dll msys-stdc++-6.dll
	do
	  cp /usr/bin/$DLLFILE $HOSTINSTALLPATH/bin
	done

	cat >$HOSTINSTALLPATH/package.json <<EOF
{
	"description": "$GCCVER $BINUTILS $GDBVER",
	"name": "toolchain-$TARGETARCHITECTURE-gcc",
	"system": [
		"windows",
		"windows_amd64",
		"windows_x86"
	],
	"url": "https://github.com/haarer/toolchain68k",
	"version": "$PACKAGEVER"
}
EOF

    log_msg " packaging..."
    cd $HOSTINSTALLPATH ;tar czf ../toolchain-$TARGETARCHITECTURE-$HOSTOS-$GCCVER.tar.gz * ; cd ..
    sha1sum toolchain-$TARGETARCHITECTURE-$HOSTOS-$GCCVER.tar.gz
}

# --------------------------------------------------------------------------------

# Copy bin files for SGDK's bin folder
copy_bin_files_for_sgdk() {

  TARGET_SGDK_FILES_PATH="sgdk_bin"
  MINGW_MINGW64_BIN=/mingw64/bin
  MINGW_USR_BIN=/usr/bin

  # Create TARGET_SGDK_FILES_PATH folder if not exists already
  if [ ! -d "$TARGET_SGDK_FILES_PATH" ]; then
      mkdir -p "$TARGET_SGDK_FILES_PATH"
  else
      rm -rf "$TARGET_SGDK_FILES_PATH"/*
  fi

  # -----------------------
  echo ">>> Copying required DLL files from MINGW to target folder..."

  MINGW_DLL_LIST="libgcc_s_seh-1.dll libstdc++-6.dll libwinpthread-1.dll libiconv-2.dll libintl-8.dll libmpc-3.dll libmpfr-6.dll libgmp-10.dll libzstd.dll msys-gcc_s-seh-1.dll msys-2.0.dll msys-stdc++-6.dll msys-iconv-2.dll msys-intl-8.dll"

  for DLL in $MINGW_DLL_LIST; do
      if [ -f "$MINGW_MINGW64_BIN/$DLL" ]; then
          echo "Copying $DLL"
          cp "$MINGW_MINGW64_BIN/$DLL" "$TARGET_SGDK_FILES_PATH/"
      elif [ -f "$MINGW_USR_BIN/$DLL" ]; then
          echo "Copying $DLL"
          cp "$MINGW_USR_BIN/$DLL" "$TARGET_SGDK_FILES_PATH/"
      else
          echo "Error: $DLL not found"
      fi
  done

  echo ">>> Done copying MINGW DLL files."

  # -----------------------
  echo ">>> Copying compatible EXE files from MINGW to target folder..."

  MINGW_EXE_LIST="mingw32-make.exe rm.exe mkdir.exe cp.exe sh.exe"
  for EXE in $MINGW_EXE_LIST; do
      if [ -f "$MINGW_MINGW64_BIN/$EXE" ]; then
          echo "Copying $EXE"
          cp "$MINGW_MINGW64_BIN/$EXE" "$TARGET_SGDK_FILES_PATH/"
      elif [ -f "$MINGW_USR_BIN/$EXE" ]; then
          echo "Copying $EXE"
          cp "$MINGW_USR_BIN/$EXE" "$TARGET_SGDK_FILES_PATH/"
      else
          echo "Error: $EXE not found"
      fi
  done

  # Rename mingw32-make.exe file to just make.exe
  echo "Renaming 'mingw32-make.exe' to 'make.exe'"
  mv "$TARGET_SGDK_FILES_PATH/mingw32-make.exe" "$TARGET_SGDK_FILES_PATH/make.exe"

  echo ">>> Done copying compatible EXE files."

  # -----------------------
  echo ">>> Copying GCC libs and exec files..."

  GCC_LIB_EXEC="$HOSTINSTALLPATH/lib/gcc/$TARGETARCHITECTURE/$GCCVER_ONLY"
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

  echo ">>> Done copying GCC libs and exec files."

  # -----------------------
  echo ">>> Copy and rename all files in bin directory by removing the 'm68k-elf-' prefix"

  GCC_BINS="$HOSTINSTALLPATH/bin"
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
      cd ..
  else
      echo "Error: GCC binaries directory not found at $GCC_BINS"
  fi

  echo ">>> Done."
}

# --------------------------------------------------------------------------------

# Build gdb
function build_gdb () {

log_msg ">>>> build gdb"

GDBFLAGS="  --target=$TARGETARCHITECTURE \
            --prefix=$HOSTINSTALLPATH/ \
            --with-gmp=$PREREQPATH/$GMPVER \
            --with-mpfr=$PREREQPATH/$MPFRVER \
            --with-expat"

conf_compile_source $GDBVER "$HOSTINSTALLPATH/bin/$TARGETARCHITECTURE-gdb.exe" "$GDBFLAGS"
}

# --------------------------------------------------------------------------------

if [ "$ACTION" = "purge" ]; then
    rm -rf $HOSTINSTALLPATH
    rm $ROOTDIR/*.log
    purge_pkg $BINUTILS
    purge_pkg $GCCVER
    purge_pkg $GDBVER
    purge_pkg $GMPVER
    purge_pkg $ISLVER
    purge_pkg $MPCVER
    purge_pkg $MPFRVER
    exit 0
fi

if [ "$ACTION" = "download" ]; then
    download_all_pkg
    exit 0
fi

if [ "$ACTION" = "build_gdb" ]; then
    build_gdb
    exit 0
fi


if [ "$ACTION" = "package" ]; then
    make_pio_package
    exit 0
fi

if [ "$ACTION" = "sgdk_files" ]; then
    copy_bin_files_for_sgdk
    exit 0
fi

# --------------------------------------------------------------------------------

export CFLAGS='-O2 -pipe'
export CXXFLAGS='-O2 -pipe'
export LDFLAGS='-s'
export DEBUG_FLAGS=''

log_msg " start of buildscript"

log_msg " building on OS: $HOSTOS for target architecture $TARGETARCHITECTURE"

[ ! -d $ROOTDIR/toolchain-cross-build ] && mkdir $ROOTDIR/toolchain-cross-build
#cd $ROOTDIR/toolchain-cross-build

# Download all sources
download_all_pkg

log_msg ">>>> build gmp"
# Next won't work due to wrong some method definitions
#GMPFLAGS=" --prefix=$PREREQPATH/$GMPVER"
#conf_compile_source $GMPVER "$PREREQPATH/$GMPVER/lib/libgmp.a" "$GMPFLAGS"
# So we'll just download the version bundled for mingw64
log_msg ">>>> copy mingw-w64-x86_64-gmp files into $PREREQPATH/$GMPVER"
pacman -Sw --noconfirm mingw-w64-x86_64-gmp
rm -rf "$PREREQPATH/$GMPVER"
mkdir -p "$PREREQPATH/$GMPVER"
tar -I zstd -xvf /var/cache/pacman/pkg/mingw-w64-x86_64-gmp-*.pkg.tar.zst -C "$PREREQPATH/$GMPVER"
mv "$PREREQPATH/$GMPVER"/mingw64/include "$PREREQPATH/$GMPVER"
mv "$PREREQPATH/$GMPVER"/mingw64/lib "$PREREQPATH/$GMPVER"
mv "$PREREQPATH/$GMPVER"/mingw64/bin "$PREREQPATH/$GMPVER"
rm -rf "$PREREQPATH/$GMPVER"/mingw64

log_msg ">>>> build isl"
ISLFLAGS=" --prefix=$PREREQPATH/$ISLVER --with-gmp-prefix=$PREREQPATH/$GMPVER"
conf_compile_source $ISLVER "$PREREQPATH/$ISLVER/lib/libisl.a" "$ISLFLAGS"

log_msg ">>>> build mpfr"
MPFRFLAGS=" --prefix=$PREREQPATH/$MPFRVER --with-gmp=$PREREQPATH/$GMPVER"
conf_compile_source $MPFRVER "$PREREQPATH/$MPFRVER/lib/libmpfr.a" "$MPFRFLAGS"

log_msg ">>>> build mpc"
MPCFLAGS=" --prefix=$PREREQPATH/$MPCVER --with-mpfr=$PREREQPATH/$MPFRVER --with-gmp=$PREREQPATH/$GMPVER"

conf_compile_source $MPCVER "$PREREQPATH/$MPCVER/lib/libmpc.a" "$MPCFLAGS"

# -------------------------------- BINUTILS --------------------------------------
# Build binutils

log_msg ">>>> build binutils"

BINUTILSFLAGS+=" --target=$TARGETARCHITECTURE --prefix=$HOSTINSTALLPATH/ --enable-plugins --disable-info --disable-manpages --without-newlib" 

conf_compile_source $BINUTILS "$HOSTINSTALLPATH/bin/$TARGETARCHITECTURE-objcopy.exe" "$BINUTILSFLAGS"

# ---------------------------------- GCC -----------------------------------------
# Build gcc: Stage 1

log_msg ">>>> build gcc stage 1"


mkdir -p $HOSTINSTALLPATH/$TARGETARCHITECTURE/usr/include

#pushd $ROOTDIR/toolchain-cross-build/$GCCVER > /dev/null
#if [ ! -d gmp ]; then
#    log_msg "fetching gcc prerequisites"
#    ./contrib/download_prerequisites
#fi
#popd > /dev/null

GCCFLAGS="  --target=$TARGETARCHITECTURE  \
            --prefix=$HOSTINSTALLPATH/    \
            --libexecdir=$HOSTINSTALLPATH/lib \
            --enable-languages=c,c++      \
            --enable-lto                  \
            --enable-plugin               \
            --with-gnu-as                 \
            --with-gnu-ld                 \
            --with-gmp=$PREREQPATH/$GMPVER   \
            --with-mpfr=$PREREQPATH/$MPFRVER \
            --with-isl=$PREREQPATH/$ISLVER   \
            --with-mpc=$PREREQPATH/$MPCVER   \
            --disable-shared              \
            --disable-decimal-float       \
            --disable-libmudflap          \
            --disable-libssp              \
            --disable-libgomp             \
            --disable-libquadmath         \
            --disable-libstdcxx-pch       \
            --disable-threads             \
            --disable-tls                 \
            --disable-nls                 \
            --disable-manpages            \
            --disable-info                \
            --disable-checking            \
            --with-sysroot=$HOSTINSTALLPATH/$TARGETARCHITECTURE \
            --without-newlib              \
            --without-headers "

SOURCEPACKAGE=$GCCVER
CONFIGURESTRING=$GCCFLAGS

[ ! -d $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj ] && mkdir $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj

pushd $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj > /dev/null

log_msg "CCS sourcepackage= $SOURCEPACKAGE=$GCCVER"
log_msg "CCS detect file= $DETECTFILE"
log_msg "CCS cfgstring $CONFIGURESTRING"

if [ ! -f config.status ]; then
    log_msg "configuring $SOURCEPACKAGE"
    ../configure $CONFIGURESTRING 2>&1 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-conf.1.log || exit 1
    log_msg "configuring $SOURCEPACKAGE finished"
else
    log_msg "configuring $SOURCEPACKAGE skipped"
fi

if [ ! -f gcc/include/limits.h ]; then
    log_msg "building $SOURCEPACKAGE"
    make -j $MAKEJOBS all-gcc 2>&1 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-build.1.log || exit 1
    if [ $? -eq 0 ]; then
        log_msg "building $SOURCEPACKAGE finished"
    else
        log_err "building $SOURCEPACKAGE failed"
    fi
else
    log_msg "building $SOURCEPACKAGE skipped"
fi

if [ ! -f $HOSTINSTALLPATH/lib/gcc/$TARGETARCHITECTURE/$GCCVER_ONLY/include/limits.h ]; then
    log_msg "install $SOURCEPACKAGE"
    make install-gcc 2>&1 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-install.1.log || exit 1
    log_msg "install $SOURCEPACKAGE finished"
else
    log_msg "install $SOURCEPACKAGE skipped"
fi
popd > /dev/null

# ---------------------------------- GCC -----------------------------------------
# Build gcc: Stage 2

log_msg ">>>> build gcc stage 2"

[ ! -d $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj2 ] && mkdir $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj2

pushd $ROOTDIR/toolchain-cross-build/$SOURCEPACKAGE/cross-chain-$TARGETARCHITECTURE-obj2 > /dev/null

log_msg "CCS sourcepackage= $SOURCEPACKAGE=$GCCVER"
log_msg "CCS cfgstring $CONFIGURESTRING"

# Must always be reconfigured (with headers now)
log_msg "configuring $SOURCEPACKAGE"
../configure $CONFIGURESTRING 2>&1 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-config.2.log || { log_err "configuring $SOURCEPACKAGE failed"; exit 1;}
log_msg "configuring $SOURCEPACKAGE finished"


log_msg "building $SOURCEPACKAGE"
make -j $MAKEJOBS 2>&1 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-build.2.log || { log_err "building $SOURCEPACKAGE failed"; exit 1;}
log_msg "building $SOURCEPACKAGE finished"

log_msg "install $SOURCEPACKAGE"
make install  2>&1 | tee -a $ROOTDIR/$SOURCEPACKAGE-$TARGETARCHITECTURE-install.2.log || { log_err "install $SOURCEPACKAGE failed";  exit 1;}
log_msg "install $SOURCEPACKAGE finished"

popd > /dev/null

# ---------------------------------- GDB -----------------------------------------
build_gdb

# -------------------------------- PACKAGE ---------------------------------------
#make_pio_package

# ---------------------------------- SGDK ----------------------------------------
copy_bin_files_for_sgdk

echo "----------------------------------------------------"
echo "Toolchain with plugin support built successfully!"
echo "Add to your PATH: ${HOSTINSTALLPATH}/bin"
echo "  export PATH=${HOSTINSTALLPATH}/bin:\$PATH"
echo "----------------------------------------------------"

m68k-elf-gcc --version
m68k-elf-as --version
m68k-elf-gdb --version
echo ""
echo "Check if plugins are supported in the linker"
m68k-elf-ld --help | grep -i plugin
echo ""
echo "Check GCC plugin support (output must be different than 'plugin')"
m68k-elf-gcc -print-file-name=plugin