# The Factory: the core and the Adapters, with a Podman client for the host's socket (ADR 0010).
# Build context: the repository root.
FROM docker.io/library/python:3.12-alpine
RUN apk add --no-cache git podman-remote && pip install --no-cache-dir jsonschema==4.25.1
COPY src /opt/asf/src
COPY adapters /opt/asf/adapters
COPY images /opt/asf/images
COPY deploy/config.json /opt/asf/config.json
RUN git config --system safe.directory '*'
ENV PYTHONPATH=/opt/asf/src PYTHONUNBUFFERED=1 PODMAN=podman-remote
CMD ["python", "-m", "factory", "--config", "/opt/asf/config.json"]
