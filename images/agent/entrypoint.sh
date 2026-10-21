#!/bin/sh
# Run Pi on the Run Context mounted at /ctx: prompt in /ctx/prompt, system prompt in /ctx/system-prompt, skills in /ctx/skills, working
# directory /ctx/cwd, session state in /ctx/session. The model server comes from the environment:
#   ASF_MODEL_ENDPOINT (an OpenAI-compatible base URL), ASF_MODEL_NAME, ASF_MODEL_CONTEXT_WINDOW.
set -eu
: "${ASF_MODEL_ENDPOINT:?}" "${ASF_MODEL_NAME:?}" "${ASF_MODEL_CONTEXT_WINDOW:?}"
mkdir -p /root/.pi/agent
# The model description the earlier experiments ran with: a thinking Qwen served through llama-server's chat template.
cat >/root/.pi/agent/models.json <<JSON
{"providers": {"local": {"baseUrl": "$ASF_MODEL_ENDPOINT", "api": "openai-completions", "apiKey": "none",
  "models": [{"id": "$ASF_MODEL_NAME", "name": "$ASF_MODEL_NAME", "input": ["text"], "reasoning": true,
    "contextWindow": $ASF_MODEL_CONTEXT_WINDOW, "maxTokens": 8192,
    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
    "compat": {"thinkingFormat": "qwen-chat-template"}}]}}}
JSON
# A queued request can wait a long time for its first byte on a shared model server.
echo '{"httpIdleTimeoutMs": 0}' >/root/.pi/agent/settings.json
git config --global safe.directory '*'
cd /ctx/cwd
# The role's skills are folders in /ctx/skills; a session already in /ctx/session is resumed.
set --
for skill in /ctx/skills/*/; do
	[ -d "$skill" ] && set -- "$@" --skill "${skill%/}"
done
[ ! -s /ctx/system-prompt ] || set -- "$@" --append-system-prompt "$(cat /ctx/system-prompt)"
[ -z "$(ls -A /ctx/session 2>/dev/null)" ] || set -- "$@" --continue
exec pi --provider local --model "$ASF_MODEL_NAME" --session-dir /ctx/session "$@" -p "$(cat /ctx/prompt)"
