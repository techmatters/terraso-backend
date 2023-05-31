FROM python:3.11.3-slim-bullseye

RUN adduser --disabled-password terraso

ENV PATH /home/terraso/.local/bin:$PATH
# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION 2.8.12

ENV DOCKER_BUILDKIT 1

RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt-get update && \
    apt-get install -q -y --no-install-recommends \
                     build-essential libpq-dev dnsutils libmagic-dev mailcap \
                     gettext software-properties-common \
                     libgdal-dev gdal-bin unzip curl && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=terraso:terraso . /app

USER terraso

RUN --mount=target=/root/.cache,type=cache,sharing=locked \
    pip install --upgrade pip && make install

RUN django-admin compilemessages --locale=es --locale=en
