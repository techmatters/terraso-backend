#!/bin/bash

docker run \
    -it \
    --rm \
    --shm-size="2g" \
    --network host \
    -v "$(pwd)/output":/app/output \
    techmatters/terraso_thumbnail_generator \
    # bash
