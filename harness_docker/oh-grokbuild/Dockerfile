FROM node:22-bookworm

# uv/uvx: Agent Canvas uses it to launch the Python agent server
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Base tooling the agent needs (agent server drives terminals through tmux)
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates tmux ripgrep procps \
    && rm -rf /var/lib/apt/lists/*

# The node image ships a uid/gid 1000 user named "node"; rename it to grok.
# Keep uid 1000 -- host user lsh is 1000 too, otherwise bind mounts aren't writable.
RUN usermod -l grok -d /home/grok -m node \
    && groupmod -n grok node

# Canvas frontend + grok-build CLI (bin name "grok", ACP entrypoint is `grok agent stdio`)
RUN npm install -g @openhands/agent-canvas@1.16.0 @xai-official/grok \
    && agent-canvas --version \
    && grok --version

# Pre-create the cache dir owned by grok: a named volume mounted here would
# otherwise be created root-owned and uv could not write to it.
RUN mkdir -p /home/grok/.cache && chown grok:grok /home/grok/.cache

USER grok
ENV HOME=/home/grok
WORKDIR /projects
EXPOSE 8888
CMD ["agent-canvas", "--port", "8888"]
