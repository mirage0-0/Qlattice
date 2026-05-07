#!/usr/bin/env bash

set -e

{
    ./scripts/setenv.default.sh
    ./scripts/qcore.sh

    rm -rfv ~/.cache/pip
    ./scripts/python.sh
    ./scripts/python-pip.sh
    ./scripts/re2c.sh
    ./scripts/ninja.sh
    ./scripts/ninja-script.sh
    ./scripts/python-meson.sh
    ./scripts/python-meson-py.sh
    ./scripts/python-packages.sh

    date
} 2>&1 | tee $prefix/log.build.txt
