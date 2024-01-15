#!/bin/bash

name=setenv-frontier-cpu

source qcore/set-prefix.sh

{ time {
    echo "!!!! build $name !!!!"
    source qcore/conf.sh

#
cat >"$prefix/setenv.sh" <<EOF
if [ -z "\$num_proc" ] ; then
    export num_proc=8
fi
module purge
module load PrgEnv-gnu
module load craype-x86-trento
module load xpmem
module load perftools-base
module list
if [ -z "\$USE_COMPILER" ] ; then
    export USE_COMPILER=gcc
fi
export CC=cc
export CXX=CC
export MPICC=cc
export MPICXX=CC
EOF

    #
    "$wd"/qcore/bin/mk-setenv-dir.sh --keep
    echo "!!!! $name build !!!!"
} } 2>&1 | tee $prefix/log.$name.txt
