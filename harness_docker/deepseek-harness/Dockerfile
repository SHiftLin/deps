FROM node:24

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      vim unzip p7zip-full jq ripgrep net-tools \
      python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @deepseek-ai/dsh

RUN mkdir -p /home/node/.dsh && chown node:node /home/node/.dsh

USER node
WORKDIR /projects
EXPOSE 8080
CMD ["dsh", "web", "--no-open", "--port", "8080"]
