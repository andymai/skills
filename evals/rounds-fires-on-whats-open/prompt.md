---
description: A request to go through all open work across repos. The rounds skill must fire.
expected_outcome: Claude invokes the rounds skill. The run has no Bash grant, so it cannot reach GitHub.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

What is open across my repos right now? Go through my PRs and branches and tell me what needs me.
