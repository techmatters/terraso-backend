FROM python:3.13.7-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN adduser --disabled-password terraso

ENV PATH=/home/terraso/.local/bin:$PATH
# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION=2.8.12

# Add Debian snapshot archive for GDAL 3.11.3 (frozen version for reproducible builds)
# Using snapshot ensures system GDAL matches Python gdal==3.11.3 bindings
RUN printf 'Types: deb\nURIs: http://snapshot.debian.org/archive/debian/20250822T205752Z/\nSuites: sid\nComponents: main\nCheck-Valid-Until: no\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' > /etc/apt/sources.list.d/snapshot.sources && \
    echo 'Package: libgdal-dev gdal-bin libgdal34t64\nPin: version 3.11.3*\nPin-Priority: 1000' > /etc/apt/preferences.d/gdal-pinned && \
    printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\n' > /etc/apt/apt.conf.d/80-retries

RUN apt-get update && \
    # Fail fast if the GDAL 3.11.3 snapshot was unreachable. snapshot.debian.org
    # is flaky (503 TooManyRequests); when it is, apt silently falls back to
    # trixie's libgdal 3.10.3 and the Python gdal==3.11.3 build breaks much later
    # with a confusing "requires at least libgdal 3.11.3" error. Abort loudly
    # here instead, so the fix (retry the build) is obvious.
    apt-cache policy libgdal-dev | grep -q 'Candidate: 3\.11\.3' || { \
        echo "ERROR: system libgdal 3.11.3 is unavailable — the Debian snapshot fetch likely failed (snapshot.debian.org 503). Retry the build." >&2; \
        apt-cache policy libgdal-dev >&2; \
        exit 1; } && \
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
