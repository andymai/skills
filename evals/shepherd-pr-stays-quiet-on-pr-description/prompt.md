---
description: A request for a PR description. That is the job of the pr-description command, so the shepherd-pr skill must not fire.
expected_outcome: Claude does not invoke the shepherd-pr skill.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a PR title and description for the changes on my branch.
