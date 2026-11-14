---
description: A request to drive the PR of the current branch to green. The shepherd-pr skill must fire.
expected_outcome: Claude invokes the shepherd-pr skill. The run has no Bash grant, so it cannot reach GitHub.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Shepherd the PR for this branch: address the review comments and get CI green.
