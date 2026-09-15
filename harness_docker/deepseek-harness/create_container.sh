#!/bin/bash
set -euo pipefail

PROJECTS_PATH="${PROJECTS_PATH:-$HOME/dsh_projects}"

# Create the host dirs as the invoking user: "docker -v" would otherwise create
# any missing one as root, leaving it unwritable inside the container.
mkdir -p "${PROJECTS_PATH}" "${HOME}/.dsh"

sudo docker run -dit --name dsh \
  --restart unless-stopped \
  --network host \
  -v "${PROJECTS_PATH}:/projects" \
  -v "${HOME}/.dsh:/home/node/.dsh" \
  deepseek-harness
