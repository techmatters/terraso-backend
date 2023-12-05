FROM python:3.12.0-slim-bullseye

RUN adduser --disabled-password terraso

ENV PATH /home/terraso/.local/bin:$PATH
ENV AWS_CLI_VERSION 2.8.12
ENV GDAL_LIBRARY_PATH /usr/local/lib/libgdal.so
ENV LD_LIBRARY_PATH /usr/local/lib

RUN apt-get update && \
    apt-get install -q -y --no-install-recommends \
                     libproj-dev proj-bin \
                     wget cmake \
                     build-essential libpq-dev dnsutils libmagic-dev mailcap \
                     gettext software-properties-common \
                     libkml-dev unzip curl && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install GDAL
RUN wget https://download.osgeo.org/gdal/3.6.4/gdal-3.6.4.tar.gz && \
    tar xzf gdal-3.6.4.tar.gz && \
    cd gdal-3.6.4 && \
    mkdir build && \
    cd build && \
    ulimit -n 1024 && \
    cmake .. && \
    cmake --build . && \
    cmake --build . --target install

WORKDIR /app

COPY --chown=terraso:terraso requirements.txt /app
COPY --chown=terraso:terraso Makefile /app

USER terraso

RUN pip install --upgrade pip && make install

COPY --chown=terraso:terraso . /app

RUN django-admin compilemessages --locale=es --locale=en
