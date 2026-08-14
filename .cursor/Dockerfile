# Cursor Cloud Agent image for hermes-agent (fork).
# Do NOT use the repo-root production Dockerfile — it builds SQLite from
# source and pulls pinned GHCR layers; recurring cloud builds fail with
# "unexpected error" / no logs when that path flakes.
# Do NOT COPY the project — Cursor checks out the commit itself.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    PATH="/root/.local/bin:${PATH}"

# git + sudo required for Cursor Cloud Agent checkout / tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      sudo \
      build-essential \
      python3 \
      python3-venv \
      python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

# uv manages the project Python (hermes requires >=3.11,<3.14)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Node 26 (matches .nvmrc)
RUN curl -fsSL https://deb.nodesource.com/setup_26.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
