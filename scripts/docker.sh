#!/bin/bash

DOCKER_ERRORS=$(docker info 2>/dev/null | grep -c ERROR)
if [ "${DOCKER_ERRORS}" = "0" ]; then
  docker compose $1 up
else
  echo "Docker is not running. Please start it and try 'make run' again."
fi
