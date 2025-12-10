# syntax=docker/dockerfile:1.7
FROM mcr.microsoft.com/devcontainers/python:3.13

ENV UV_PROJECT_ENVIRONMENT=.venv

# Install base dependencies and libraries required by Home Assistant
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    git \
    gnupg \
    libpcap-dev \
    libturbojpeg0 \
    pkg-config \
    unzip \
    xz-utils && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js (latest LTS) for Copilot CLI
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends gh && \
    rm -rf /var/lib/apt/lists/*

# Install uv globally so it's available to all users
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    chmod 755 /usr/local/bin/uv

# Install GitHub Copilot CLI and additional Node.js tools
RUN npm install -g @githubnext/github-copilot-cli && \
    npm install -g yarn && \
    npm cache clean --force

# Switch to vscode user and set up their environment
USER vscode
ENV PATH="/home/vscode/.local/bin:${PATH}"

# Install uv for vscode user as well
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Switch back to root for any final setup (devcontainer will switch to vscode)
USER root
