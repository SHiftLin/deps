#!/bin/bash
set -euo pipefail

# sudo docker build \
#   --build-arg OPENCODE_UID="$(id -u)" \
#   --build-arg OPENCODE_GID="$(id -g)" \
#   -t opencode

PROJECTS_PATH="${PROJECTS_PATH:-$HOME/oc_projects}"

mkdir -p ${PROJECTS_PATH} ${HOME}/.opencode

sudo docker run -dit --name opencode --restart unless-stopped \
  -p 4096:4096 \
  -v "${PROJECTS_PATH}:/projects" \
  -v "${HOME}/.opencode:/home/opencode/.local/share/opencode" \
  opencode
