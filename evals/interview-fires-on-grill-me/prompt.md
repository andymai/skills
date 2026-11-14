---
description: A request to be grilled on a plan. The interview skill must fire.
expected_outcome: Claude invokes the interview skill and asks its first round of questions. It writes no plan.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Grill me on this plan before I start. I want to move our session storage from Postgres to Redis next sprint.
