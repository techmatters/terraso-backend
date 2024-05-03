FROM python:3.12.3-alpine3.19

RUN adduser --disabled-password terraso

ENV PATH /home/terraso/.local/bin:$PATH
# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION 2.8.12

RUN apk add --quiet --no-cache --upgrade \
    bind-tools build-base curl gcc gdal gdal-dev geos-dev gettext gfortran \
    libffi-dev libkml-dev libmagic libpq mailcap openblas-dev postgresql-dev proj-dev \
    proj-util unzip && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && ./aws/install

WORKDIR /app

COPY --chown=terraso:terraso requirements.txt /app
COPY --chown=terraso:terraso Makefile /app

USER terraso

RUN pip install --upgrade pip && make install

COPY --chown=terraso:terraso . /app

RUN django-admin compilemessages --locale=es --locale=en
