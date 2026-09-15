#!/bin/bash
# Create the grokbuild container (Agent Canvas + grok-build CLI).
# Recreating: docker rm -f grokbuild, then run this again.
set -euo pipefail

PROJECTS_PATH="${PROJECTS_PATH:-$HOME/grok_projects}"

# Create the host dirs as the invoking user: "docker -v" would otherwise create
# any missing one as root, leaving it unwritable inside the container.
mkdir -p "${PROJECTS_PATH}" "${HOME}/.grokbuild" "${HOME}/.oh-grok"

sudo docker run -dit --name grokbuild --restart unless-stopped \
  -p 8888:8888 \
  -v "${PROJECTS_PATH}:/projects" \
  -v "${HOME}/.grokbuild:/home/grok/.grok" \
  -v "${HOME}/.oh-grok:/home/grok/.openhands" \
  -v grokbuild-cache:/home/grok/.cache \
  grokbuild
