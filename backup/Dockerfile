FROM debian:buster-slim

RUN apt-get update && apt-get install -y curl unzip jq \
          && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
          && unzip awscliv2.zip \
          && ./aws/install

COPY backup.sh /script/backup.sh

ENTRYPOINT ["/script/backup.sh"]
