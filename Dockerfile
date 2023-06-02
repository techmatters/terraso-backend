FROM python:3.11.3-slim-bullseye

RUN adduser --disabled-password terraso

ENV PATH /home/terraso/.local/bin:$PATH

RUN apt-get update
RUN apt-get install -q -y --no-install-recommends \
                     build-essential libpq-dev dnsutils libmagic-dev mailcap \
                     gettext software-properties-common \
                     libgdal-dev gdal-bin unzip curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -O "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" && \
    unzip awscli-exe-linux-x86_64.zip && \
    ./aws/install

WORKDIR /app

COPY --chown=terraso:terraso requirements.txt /app
COPY --chown=terraso:terraso Makefile /app

USER terraso

RUN pip install --upgrade pip && make install

COPY --chown=terraso:terraso . /app

RUN django-admin compilemessages --locale=es --locale=en
