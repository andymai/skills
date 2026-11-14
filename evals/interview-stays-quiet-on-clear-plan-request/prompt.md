---
description: A clear request for an implementation plan. Nobody asked for an interview, so the interview skill must not fire.
expected_outcome: Claude writes the plan and does not invoke the interview skill.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write an implementation plan for rate limiting on our API. The limit is 100 requests each minute for each API key. A request over the limit gets a 429 response with a Retry-After header.
