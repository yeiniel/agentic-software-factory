#!/bin/sh
# Run Pi on the Run Context mounted at /ctx: prompt in /ctx/prompt.md, clone in /ctx/work,
# session state in /ctx/session. The model server comes from the environment:
#   ASF_MODEL_ENDPOINT (an OpenAI-compatible base URL), ASF_MODEL_NAME, ASF_MODEL_CONTEXT_WINDOW.
set -eu
: "${ASF_MODEL_ENDPOINT:?}" "${ASF_MODEL_NAME:?}" "${ASF_MODEL_CONTEXT_WINDOW:?}"
mkdir -p /root/.pi/agent
cat > /root/.pi/agent/models.json <<JSON
{"providers": {"local": {"baseUrl": "$ASF_MODEL_ENDPOINT", "api": "openai-completions", "apiKey": "none",
  "models": [{"id": "$ASF_MODEL_NAME", "contextWindow": $ASF_MODEL_CONTEXT_WINDOW}]}}}
JSON
git config --global safe.directory '*'
cd /ctx/work
resume=
[ -z "$(ls -A /ctx/session 2> /dev/null)" ] || resume=--continue
# shellcheck disable=SC2086
exec pi --provider local --model "$ASF_MODEL_NAME" --session-dir /ctx/session $resume -p "$(cat /ctx/prompt.md)"
