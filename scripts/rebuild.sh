#!/bin/bash
set -e

build_hash()
{
    if [ -z $(which md5sum) ]; then
        # macOS support
        md5 -r requirements/base.in requirements/deploy.in requirements/dev.in requirements.txt requirements-dev.txt > .rebuild
    else
        # Linux support
        md5sum requirements/base.in requirements/deploy.in requirements/dev.in requirements.txt requirements-dev.txt > .rebuild
    fi
}

check_hash()
{
    if [ -z $(which md5sum) ]; then
        # macOS support
        md5 -r requirements/base.in requirements/deploy.in requirements/dev.in requirements.txt requirements-dev.txt | diff .rebuild - > /dev/null 2>&1
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
