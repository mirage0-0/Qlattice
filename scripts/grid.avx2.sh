#!/bin/bash

name=Grid

source qcore/set-prefix.sh $name

{ time {

    echo "!!!! build $name !!!!"

    source qcore/conf.sh ..

    mkdir -p "$prefix"/src || true

    rsync -av --delete $distfiles/$name/ "$prefix"/src

    cd "$prefix/src"

    INITDIR="$(pwd)"
    rm -rfv "${INITDIR}/Eigen/Eigen/unsupported"
    rm -rfv "${INITDIR}/Grid/Eigen"
    ln -vs "${INITDIR}/Eigen/Eigen" "${INITDIR}/Grid/Eigen"
    ln -vs "${INITDIR}/Eigen/unsupported/Eigen" "${INITDIR}/Grid/Eigen/unsupported"

    export CXXFLAGS="$CXXFLAGS -fPIC -w -Wno-psabi"

    mkdir build
    cd build
    ../configure \
        --enable-simd=AVX2 \
        --enable-alloc-align=4k \
        --enable-comms=mpi-auto \
        --enable-gparity=no \
        --prefix="$prefix"

    make -j$num_proc
    make install

    cd "$wd"

    mk-setenv.sh

    echo "!!!! $name build !!!!"

    rm -rf "$temp_dir" || true

} } 2>&1 | tee "$prefix/log.$name.txt"
