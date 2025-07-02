#!/usr/bin/env bash
set -euo pipefail

if [ $# != 0 ]; then
    echo "Usage: $0"
    exit 1;
fi

boost_version=1.81.0
boost_dir="boost-${boost_version}"
boost_archive="${boost_dir}.tar.gz"
boost_build="boost_${boost_version//./_}_build"

# 下載 Boost 壓縮檔
if [ ! -d "${boost_dir}" ]; then
    if [ ! -e "${boost_archive}" ]; then
        wget "https://github.com/boostorg/boost/releases/download/boost-${boost_version}/${boost_archive}"
    fi
    tar xvf "${boost_archive}"
fi

# 編譯 Boost
if [ ! -d "${boost_build}" ]; then
    (
        set -euo pipefail
        cd "${boost_dir}"
        ./bootstrap.sh
        ./b2 install --prefix=$(pwd)/../"${boost_build}" install
    )
fi

# 下載 & 編譯 KenLM
if [ ! -d kenlm ]; then
    git clone https://github.com/kpu/kenlm.git
fi

(
    set -euo pipefail
    cd kenlm
    mkdir -p build
    (
        set -euo pipefail
        cd build
        cmake -DCMAKE_PREFIX_PATH=$(pwd)/../../"${boost_build}" ..
        make -j$(nproc)
    )
    (
        set -euo pipefail
        python3 -m pip install -e .
    )
)
