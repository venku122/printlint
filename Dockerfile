# syntax=docker/dockerfile:1
FROM node:26.13.0-bookworm-slim@sha256:bc0a2afd3b74ce12222fc8bab99271e66257f021078f5f4a5d687a77d280c1d9 AS node
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv
FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS build
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=uv /uv /usr/local/bin/uv
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && apt-get update && apt-get install -y --no-install-recommends git ca-certificates libstdc++6 libatomic1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/printlint
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY pyproject.toml uv.lock dependencies.json ./
COPY src/ src/
COPY config/ config/
COPY plugins/ plugins/
COPY tests/ tests/
COPY tools/ tools/
COPY docs/validation-status.json docs/validation-status.json
RUN ./tools/setup.sh

FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 libatomic1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/node /usr/local/bin/node
COPY --from=build /opt/printlint /opt/printlint
ENV PATH="/opt/printlint/.venv/bin:$PATH" HOME=/tmp PYTHONDONTWRITEBYTECODE=1
WORKDIR /models
USER 65532:65532
ENTRYPOINT ["/opt/printlint/.venv/bin/printlint"]
CMD ["--help"]
