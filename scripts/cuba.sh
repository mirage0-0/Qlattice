#!/bin/bash

. conf.sh

name=Cuba
echo "!!!! build $name !!!!"

rm -rf $src_dir
mkdir -p $src_dir
cd $src_dir
tar xaf $distfiles/$name-*.tar.*

cd $name-*
./configure \
    --prefix=$prefix
make
make install

cd $wd
echo "!!!! $name build !!!!"

rm -rf $temp_dir
