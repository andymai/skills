---
description: A request for prose that a person reads. That is not a document for an agent, so the agent-docs skill must not fire.
expected_outcome: Claude does not invoke the agent-docs skill.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a short README section that explains how to install this CLI with npm.
