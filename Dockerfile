FROM python:3.12.0-slim-bullseye

RUN adduser --disabled-password terraso

ENV PATH /home/terraso/.local/bin:$PATH
# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION 2.8.12
ENV GDAL_LIBRARY_PATH /usr/local/lib/libgdal.so
ENV LD_LIBRARY_PATH /usr/local/lib
ENV GDAL_CONFIG /usr/bin/gdal-config
ENV GDAL_DATA /usr/share/gdal
ENV CPLUS_INCLUDE_PATH /usr/include/gdal
ENV C_INCLUDE_PATH /usr/include/gdal

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

# Create and activate a virtual environment
RUN python -m venv /home/terraso/venv
ENV PATH="/home/terraso/venv/bin:$PATH"

COPY --chown=terraso:terraso requirements.txt /app
COPY --chown=terraso:terraso Makefile /app

RUN pip install --upgrade pip && make install

RUN ogrinfo --formats | grep KML
RUN gdalinfo --version || echo 'GDAL is not installed'
RUN gdal-config --version || echo 'GDAL is not installed'
RUN fio --gdal-version || echo 'GDAL is not installed'
RUN echo "GDAL_VERSION is set to ${GDAL_VERSION}"

USER terraso

COPY --chown=terraso:terraso . /app

RUN django-admin compilemessages --locale=es --locale=en
