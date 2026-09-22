#!/bin/bash
set -euo pipefail

PROJECTS_PATH="${PROJECTS_PATH:-$HOME/oh_projects}"

# Create the host dirs as the invoking user: "docker -v" would otherwise create
# any missing one as root, leaving it unwritable inside the container.
mkdir -p "${PROJECTS_PATH}" "${HOME}/.openhands"

sudo docker run -dit --name openhands \
  --restart unless-stopped \
  -p 8000:8000 \
  -v "${PROJECTS_PATH}:/projects" \
  -v "${HOME}/.openhands:/home/openhands/.openhands" \
  ghcr.io/openhands/agent-canvas:latest


# mac
# docker run -dit  --name openhands \
#   -v /var/run/docker.sock:/var/run/docker.sock \
#   -v $HOME/.openhands:/.openhands \
#   -p 8000:8000 \
#   ghcr.io/openhands/agent-canvas:latest