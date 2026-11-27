#!/bin/bash

docker build --platform=linux/arm64/v8 --tag=techmatters/terraso_thumbnail_generator --file=Dockerfile .
