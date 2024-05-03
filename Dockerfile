FROM ghcr.io/osgeo/gdal:ubuntu-full-latest

ENV PATH /home/terraso/.local/bin:$PATH
# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION 2.8.12

RUN apt-get update && \
    apt-get install -q -y --no-install-recommends software-properties-common

# prevent tzdata from prompting
RUN ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime

RUN apt-get update && \
    apt-get install -q -y --no-install-recommends \
                     python3.12 python3.12-dev \
                     build-essential libpq-dev dnsutils libmagic-dev mailcap \
                     gettext \
                     libkml-dev unzip curl && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /root/.config/pip && echo "[global]" > /root/.config/pip/pip.conf && echo "break-system-packages = true" >> /root/.config/pip/pip.conf
RUN curl -s https://bootstrap.pypa.io/get-pip.py | python3.12

RUN adduser --disabled-password terraso

WORKDIR /app

COPY --chown=terraso:terraso requirements.txt /app
COPY --chown=terraso:terraso Makefile /app

USER terraso

RUN pip config set global.break-system-packages true

# there is no python3.12-pytest, so install manually
RUN pip install pytest
RUN pip install --upgrade pip && make install

COPY --chown=terraso:terraso . /app

RUN django-admin compilemessages --locale=es --locale=en
