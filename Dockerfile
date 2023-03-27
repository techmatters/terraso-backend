FROM python:3.11.2-slim-bullseye

RUN adduser --disabled-password terraso

ENV PATH /home/terraso/.local/bin:$PATH
# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION 2.8.12

RUN apt-get update && \
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

RUN pip install --upgrade pip && make install

RUN python terraso_backend/manage.py compilemessages

