"""Turning the Factory's events and Pi's session entries into one line of text each."""
import json

CLIP = 2000
HIDDEN = ("kind", "trace", "run", "stream", "task", "output")


def clip(text, n=CLIP):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + "..."


def render_event(kind, attrs):
    """`kind key=value ...`; the Feedback text is the point of its events, so it is shown whole."""
    fields = {k: v for k, v in attrs.items() if k not in HIDDEN}
    feedback = fields.pop("feedback", None)
    if feedback is None:
        feedback = next((v for k, v in sorted(fields.items()) if k.startswith("feedback.")), None)
        fields = {k: v for k, v in fields.items() if not k.startswith("feedback.")}
    head = " ".join(f"{k}={clip(v, 80)}" for k, v in fields.items())
    text = f"{kind} {head}".rstrip()
    return f"{text}: {feedback}" if feedback else text


def render_transcript(line):
    """Pi session entry -> readable lines; anything but a message is skipped."""
    try:
        entry = json.loads(line)
        message = entry["message"] if entry.get("type") == "message" else None
        content = message["content"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return []
    if not isinstance(content, list):
        content = [{"type": "text", "text": content}]
    out = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and message.get("role") == "assistant":
            out.append(f"says: {clip(part.get('text', ''))}")
        elif part.get("type") == "text" and message.get("role") == "toolResult":
            out.append(f"{message.get('toolName')} returned: {clip(part.get('text', ''), 400)}")
        elif part.get("type") == "toolCall":
            out.append(f"calls {part.get('name')} {clip(json.dumps(part.get('arguments')), 400)}")
    return out
