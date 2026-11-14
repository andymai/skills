---
description: A request for a reply to a PR reviewer. The outward-writing skill must fire.
expected_outcome: Claude invokes the outward-writing skill before it writes the reply.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

A reviewer on my pull request asked why I replaced the retry loop with a queue. Write the reply for me. The reason is that the retry loop blocked the request thread for up to 30 seconds.
