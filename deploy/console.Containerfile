# The Console's receiver (OTLP in, API out). Standard library only; the TUI runs on the host (bin/console).
# Build context: the repository root.
FROM docker.io/library/python:3.12-alpine
COPY console/asf_console /opt/asf-console/asf_console
ENV PYTHONPATH=/opt/asf-console PYTHONUNBUFFERED=1 CONSOLE_DATA=/var/lib/asf/console
CMD ["python", "-m", "asf_console.receiver", "--otlp-host", "0.0.0.0", "--api-host", "0.0.0.0"]
