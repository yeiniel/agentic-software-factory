# The one way out of the Agents' network: a TCP relay to the model server on the host.
FROM docker.io/library/alpine:3.22
RUN apk add --no-cache socat
ENV MODEL_SERVER=host.containers.internal:8080
CMD ["sh", "-c", "exec socat tcp-listen:8080,fork,reuseaddr tcp:$MODEL_SERVER"]
