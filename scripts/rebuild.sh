#!/bin/bash
set -e

build_hash()
{
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS support
        md5 -r pyproject.toml uv.lock > .rebuild
    else
        # Linux support
        md5sum pyproject.toml uv.lock > .rebuild
    fi
}

check_hash()
{
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS support
        md5 -r pyproject.toml uv.lock | diff .rebuild - > /dev/null 2>&1
        echo $?
    else
        # Linux support
        md5sum --quiet -c .rebuild > /dev/null 2>&1
        echo $?
    fi
}

echo "Checking if we need a docker images rebuild before running this command"
if [ $(check_hash) != 0 ]; then
    make build
    build_hash
fi
