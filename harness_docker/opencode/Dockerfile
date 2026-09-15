FROM ghcr.io/anomalyco/opencode:latest

USER root
RUN apk add --no-cache bash

ARG OPENCODE_UID=1000
ARG OPENCODE_GID=1000

RUN addgroup -g "${OPENCODE_GID}" opencode \
    && adduser -D -u "${OPENCODE_UID}" -G opencode \
       -h /home/opencode -s /bin/bash opencode \
    && mkdir -p /projects \
    && chown opencode:opencode /projects

ENV HOME=/home/opencode

USER opencode

RUN mkdir -p /home/opencode/.local/share/opencode

WORKDIR /projects

CMD ["serve", "--hostname", "0.0.0.0", "--port", "4096"]
