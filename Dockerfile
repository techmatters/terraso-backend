FROM python:3.11.3-slim-bullseye as build

# see https://github.com/aws/aws-cli/tags for list of versions
ENV AWS_CLI_VERSION 2.8.12

RUN adduser --disabled-password terraso

RUN apt-get update
RUN apt-get install -q -y --no-install-recommends \
                     build-essential libpq-dev dnsutils libmagic-dev mailcap \
                     gettext software-properties-common \
                     libgdal-dev gdal-bin unzip curl

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install

WORKDIR /app

COPY --chown=terraso:terraso requirements.txt /app
COPY --chown=terraso:terraso Makefile /app

USER terraso

# I'm not really a fan of using make in a circular dependency.
# We are using make to do docker build and thne also using make
# inside of the dockerfile to install requirements. I don't have
# specific fears, but it gives me a gut "anti-pattern" feel. But
# it's the easiest way to get the job done for now (rbd - 2023-06-05)
RUN pip install --upgrade pip && make install

# This creates a new image layer from scratch and only copies the files we need
# after build to reduce the final image size
FROM python:3.11.3-slim-bullseye

COPY --from=build /usr/local/bin/aws /usr/local/bin/aws
COPY --from=build /usr/bin /usr/bin
COPY --from=build /usr/lib /usr/lib
COPY --from=build /usr/local/lib /usr/local/lib

RUN adduser --disabled-password terraso

ENV PATH /home/terraso/.local/bin:$PATH

COPY --from=build /home/terraso/ /home/terraso/

USER terraso

COPY --chown=terraso:terraso . /app

WORKDIR /app

RUN django-admin compilemessages --locale=es --locale=en
