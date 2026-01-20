#!/bin/bash

# First convert Windows EOL (CRLF) to Linux EOL (LF)
#   sed -i 's/\r$//' build_python_static_lib.sh
# chmod +x build_python_static_lib.sh
# ./build_python_static_lib.sh

PY_VER=3.10.14
PY_PREFIX=/opt/python3.10-static
OPENSSL_VER=1.1.1w
OPENSSL_PREFIX=/opt/openssl-1.1.1-static
JOBS=$(nproc)

clean_files() {
  rm -rf /tmp/Python-${PY_VER} 2>/dev/null
  rm -rf /tmp/openssl-${OPENSSL_VER} 2>/dev/null
}

# Install dependencies in WSL
install_deps() {
  echo "[INFO] Installing dependencies ..."
  sudo apt update
  sudo apt install -y \
    build-essential \
    wget \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libffi-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    libgdbm-dev \
    liblzma-dev \
    uuid-dev \
    tk-dev

  if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies"
    exit 1
  fi
}

# Install all deps
install_deps
# Clean any existing src and build folder and files
clean_files

echo "[INFO] Downloading openssl $OPENSSL_VER ..."
cd /tmp
wget https://www.openssl.org/source/openssl-${OPENSSL_VER}.tar.gz
tar xf openssl-${OPENSSL_VER}.tar.gz
cd openssl-${OPENSSL_VER}

./Configure linux-x86_64 \
  no-shared \
  no-tests \
  --prefix=${OPENSSL_PREFIX}
if [ $? -ne 0 ]; then
  echo "[ERROR] Configuration for openssl $OPENSSL_VER failed"
  clean_files
  exit 1
fi

make -j${JOBS}
if [ $? -ne 0 ]; then
  echo "[ERROR] OpenSSL $OPENSSL_VER build failed"
  clean_files
  exit 1
fi

sudo make install_sw
if [ $? -ne 0 ]; then
  echo "[ERROR] OpenSSL $OPENSSL_VER installation failed"
  clean_files
  exit 1
fi

echo "[INFO] Downloading python $PY_VER ..."
cd /tmp
wget https://www.python.org/ftp/python/${PY_VER}/Python-${PY_VER}.tgz
tar xf Python-${PY_VER}.tgz
cd Python-${PY_VER}

# Clean environment to avoid accidental shared linking
export CFLAGS="-O2 -fPIC"
export CPPFLAGS="-I${OPENSSL_PREFIX}/include"
export LDFLAGS="-L${OPENSSL_PREFIX}/lib -static"
export PKG_CONFIG=""

./configure \
  --prefix=${PY_PREFIX} \
  --disable-shared \
  --enable-optimizations \
  --with-openssl=${OPENSSL_PREFIX} \
  --with-ensurepip=no

make -j${JOBS}
if [ $? -ne 0 ]; then
  echo "[ERROR] Python $PY_VER build failed"
  clean_files
  exit 1
fi

sudo make install
if [ $? -ne 0 ]; then
  echo "[ERROR] Python $PY_VER installation failed"
  clean_files
  exit 1
fi