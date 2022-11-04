FROM python:3.10-slim-bullseye

RUN adduser --disabled-password terraso

ENV PATH /home/terraso/.local/bin:$PATH

RUN apt-get update && \
    apt-get install -q -y --no-install-recommends build-essential libpq-dev dnsutils libmagic-dev mailcap unzip curl && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=terraso:terraso . /app

USER terraso

RUN pip install --upgrade pip && make install
