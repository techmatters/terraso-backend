FROM python:3.13.2-slim-bookworm

RUN adduser --disabled-password terraso

ENV PATH=/home/terraso/.local/bin:$PATH
# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION=2.8.12

ENV UV_PROJECT_ENVIRONMENT="/usr/local"

# Add testing sources and pin the GDAL packages to testing
# Allows us to get 3.9.x versions of GDAL
RUN sed 's/bookworm/testing/g' /etc/apt/sources.list.d/debian.sources >  /etc/apt/sources.list.d/testing.sources

RUN echo 'Package: libgdal-dev gdal-bin\nPin: release a=testing\nPin-Priority: 900' > /etc/apt/preferences.d/gdal-testing

RUN apt-get update && \
    apt-get install -q -y --no-install-recommends \
                     build-essential libpq-dev dnsutils libmagic-dev mailcap \
                     gettext software-properties-common \
                     libkml-dev libgdal-dev gdal-bin unzip curl && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=terraso:terraso requirements.txt /app
COPY --chown=terraso:terraso Makefile /app

USER terraso

RUN pip install --upgrade pip uv && make install

COPY --chown=terraso:terraso . /app

RUN django-admin compilemessages --locale=es --locale=en
