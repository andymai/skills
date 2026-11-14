---
description: A request to create a Claude Code skill. The agent-docs skill must fire.
expected_outcome: Claude invokes the agent-docs skill before it drafts the skill. The run has no Write grant, so it cannot save the file.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Create a new Claude Code skill for this project. It must format the SQL files in the repo with sqlfluff when I ask for it.
