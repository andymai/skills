---
name: retrospective
description: Review a coding session and propose changes to the agent's environment (checks, rules files, skills, tools) that make the next session better.
argument-hint: "[session or transcript to review; default is this session]"
disable-model-invocation: true
---

# Retrospective

Find where the session lost time or made a mistake, and propose a change to the
environment that prevents each one. The environment is everything that the agent works
with: automated checks, rules files, skills, agents, tools, and access to information.
You propose changes. You apply a change only after the user selects it.

The session to review, if the user named one: $ARGUMENTS

## 1. Load the writing rules

Invoke the `team:agent-docs` skill with the Skill tool. Each change that you
propose to a rules file, a skill, or an agent must follow those rules.

## 2. Read the session

If the line above is empty, review the current conversation. If the user named a
different session and you do not have its transcript, ask for the path. Do not guess
which transcript the user means.

Read the project's rules files (`CLAUDE.md`, `AGENTS.md`) and find the project's check
command and its CI workflow. You need them to tell a new check from a check that exists
and does not run.

## 3. Find the candidates

Look for each of these seven types. For each candidate, record the moment in the session
that shows the cost: the tool call, the error, or the user's correction. Quote it. A
candidate with no such moment is a guess, so drop it.

| Type | The session shows | Possible change |
|---|---|---|
| Navigation | Many searches to find one file or one fact | A pointer in a rules file to that location |
| Automated check | A mistake that a linter, a type check, a test, or a hook can catch | A new check, or a check that exists and is not wired into CI or a hook |
| Review rule | The reviewer did not catch a mistake that needs judgment | A new or clearer rule for the reviewer |
| Rules file | An instruction that the agent did not follow, or a rules file so long that instructions get lost | Move the instruction to a check or to the reviewer, or delete it |
| Tool cost | A tool call that returned much more than the agent needed | A narrower command, a script, or a filter |
| No-op | An instruction that does not change what the agent does | Delete it |
| Information access | The agent did not have a fact that it needed (a log, a service, a doc) | Read access to that source |

## 4. Select the layer for each change

Put each change in the first layer of this list that can hold it:

1. **An automated check**: a lint rule, a type, a test, a pre-commit hook, a CI job. Use
   this layer for each mechanical rule: a banned call, an import shape, a file location,
   a naming pattern. A check cannot forget, and it costs no context.
2. **A rule for the reviewer**: use this layer for a rule that needs judgment across
   files. The reviewer reads a diff, so it has the most room for rules.
3. **A skill or a reference file behind a pointer**: use this layer for a procedure that
   only some sessions need.
4. **A line in an always-loaded rules file**: use this layer last. Each line costs
   context in every session.

Example. The agent used `sed` on a source file, and the rules file bans that.

- Bad: add "IMPORTANT: never use sed" to the rules file a second time.
- Good: add a pre-tool hook that rejects a `sed -i` command on a tracked file, and
  delete the line from the rules file.

## 5. Present the candidates

List the candidates with the largest cost first. For each one, give:

- **Observation**: the quoted moment from the session, and how many times it occurred.
- **Change**: the exact file, and the text or the check to add, change, or delete.
- **Layer**: which of the four layers, and why a higher layer cannot hold it.
- **Cost**: what the change adds (context, run time, maintenance).

End with the candidates that you dropped and why. Then ask which changes the user wants,
and end your turn.

## 6. Apply what the user selects

When the user selects changes, apply only those changes. Follow the `team:agent-docs`
rules for each rules file, skill, or agent that you change. Run the project's checks
after the last change. Then report each file that you changed and the result of the
checks. If the user selects nothing, change nothing.

## Final self-check

- [ ] Each candidate quotes a moment from the session.
- [ ] Each mechanical rule goes to an automated check, not to prose.
- [ ] No candidate adds a line to an always-loaded file when a lower-cost layer can hold it.
- [ ] Each proposed change names an exact file and exact text.
- [ ] You changed no file before the user selected a change, and you changed only what
  the user selected.
