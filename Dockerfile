FROM python:3.13.7-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN adduser --disabled-password terraso

ENV PATH=/home/terraso/.local/bin:$PATH
# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION=2.8.12

# Add Debian snapshot archive for GDAL 3.11.3 (frozen version for reproducible builds)
# Using snapshot ensures system GDAL matches Python gdal==3.11.3 bindings
RUN printf 'Types: deb\nURIs: http://snapshot.debian.org/archive/debian/20250822T205752Z/\nSuites: sid\nComponents: main\nCheck-Valid-Until: no\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' > /etc/apt/sources.list.d/snapshot.sources && \
    echo 'Package: libgdal-dev gdal-bin libgdal34t64\nPin: version 3.11.3*\nPin-Priority: 1000' > /etc/apt/preferences.d/gdal-pinned

RUN apt-get update && \
    apt-get install -q -y --no-install-recommends \
                     build-essential libpq-dev dnsutils libmagic-dev mailcap gettext \
                     libkml-dev libgdal-dev gdal-bin unzip curl ca-certificates && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=terraso:terraso requirements.txt /app
COPY --chown=terraso:terraso Makefile /app

USER terraso

RUN uv venv /home/terraso/venv
ENV VIRTUAL_ENV=/home/terraso/venv
ENV PATH="/home/terraso/venv/bin:$PATH"

RUN make install
COPY --chown=terraso:terraso . /app

RUN django-admin compilemessages --locale=es --locale=en
