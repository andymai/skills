---
description: A request to drive the PR of the current branch to green. That is the job of the shepherd-pr skill, so the rounds skill must not fire.
expected_outcome: Claude does not invoke the rounds skill.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Shepherd the PR for this branch: address the review comments and get CI green.
