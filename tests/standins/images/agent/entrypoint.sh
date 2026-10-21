#!/bin/sh
# shellcheck disable=SC2012
# The stub reports names for a test to read, not for a script to parse.
# Stub for the agent harness entrypoint: reports its surroundings, edits the work tree, may hang.
echo "model=$ASF_MODEL_ENDPOINT $ASF_MODEL_NAME $ASF_MODEL_CONTEXT_WINDOW"
echo "interfaces=$(ls /sys/class/net | tr '\n' ' ')"
echo "env=$(env | grep -ci 'git\(_\|hub\)token\|credential')"
echo "remotes=$(git -C /ctx/cwd remote | wc -l)"
echo "prompt=$(cat /ctx/prompt)"
echo "skills=$(ls /ctx/skills 2>/dev/null | tr '\n' ' ')"
echo "session=$(ls /ctx/session | wc -l)"
echo stub >/ctx/cwd/stub.txt
echo '{"stub": true}' >/ctx/session/session.jsonl
case "$(cat /ctx/prompt)" in *HANG*) sleep 60 ;; *FAIL*) exit 3 ;; esac
