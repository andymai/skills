---
description: A request for a Slack message to a team. The outward-writing skill must fire.
expected_outcome: Claude invokes the outward-writing skill before it writes the message.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Draft a Slack message to my team. The deploy moves from Tuesday to Thursday, because the database migration needs one more review.
