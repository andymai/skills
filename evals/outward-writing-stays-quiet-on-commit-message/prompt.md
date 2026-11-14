---
description: A request for a commit message. The outward-writing description excludes commit messages, so the skill must not fire.
expected_outcome: Claude writes the commit message and does not invoke the outward-writing skill.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write me a commit message for this change: I renamed getUser to fetchUser and updated the three call sites.
