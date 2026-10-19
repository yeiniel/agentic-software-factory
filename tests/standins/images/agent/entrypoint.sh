# Stub for the agent harness entrypoint: reports its surroundings, edits the work tree, may hang.
echo "model=$ASF_MODEL_ENDPOINT $ASF_MODEL_NAME $ASF_MODEL_CONTEXT_WINDOW"
echo "interfaces=$(ls /sys/class/net | tr '\n' ' ')"
echo "mounts=$(grep ' /ctx' /proc/mounts | cut -d' ' -f2 | tr '\n' ' ')"
echo "env=$(env | grep -ci 'git\(_\|hub\)token\|credential')"
echo "remotes=$(git -C /ctx/work remote | wc -l)"
echo "prompt=$(cat /ctx/prompt.md)"
echo "session=$(ls /ctx/session | wc -l)"
echo stub > /ctx/work/stub.txt
echo '{"stub": true}' > /ctx/session/session.jsonl
case "$(cat /ctx/prompt.md)" in *HANG*) sleep 60 ;; *FAIL*) exit 3 ;; esac
