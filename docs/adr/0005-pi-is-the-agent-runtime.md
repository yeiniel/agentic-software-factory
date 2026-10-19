# Pi is the agent runtime

Agents are instances of the Pi coding agent (pi.dev). The Factory adds orchestration around it and does not write its own agent loop. This is a lock-in choice: Pi's session model, skill format and prompt interface shape the Agent boundary. Claude Code and the Agent SDK were the alternatives; we picked Pi.
