---
name: handoff
description: Write a handoff document from the current conversation, so that a new session can continue the work.
argument-hint: "[what the next session will do]"
disable-model-invocation: true
---

# Handoff

Write one document that lets an agent with no memory of this conversation continue the
work. The reader has only the document and the repo.

The focus of the next session, if the user gave one: $ARGUMENTS

If that line is empty, write for a session that continues the current task.

## 1. Collect the state

Get each item from what you observed in this session, not from memory of what you
intended. Run the command when a command can answer.

- **Repo state**: run `git status --short` and `git branch --show-current`. Record the
  branch, the last commit, and the uncommitted files.
- **Goal**: what the user asked for, in one or two sentences, in the user's words.
- **Done**: each completed part, with the evidence (the test summary line, the commit).
- **In progress**: the part that is not complete, and the exact point where it stopped.
- **Not started**: the parts that remain.

## 2. Write the document

Use these sections, in this order. Leave out a section that has no content.

```
# Handoff: <task>

## Goal
## State
## Next step
## Decisions
## Dead ends
## Open questions
## Pointers
## Skills to use
```

Rules for each section:

- **State**: label each claim **verified** (you ran a command and read the output),
  **inferred** (you read code that implies it), or **assumed**. Quote the summary line of
  the last test run. A reader acts on "tests pass" as a fact, so do not write it unless
  you saw it.
- **Next step**: one action that the reader can start with no more questions. Give the
  file, the function, and the command. "Continue the refactor" is not a next step.
- **Decisions**: each decision with its reason, so that the reader does not reopen it.
- **Dead ends**: each approach that failed, with the error or the reason. This section
  stops the next session from a repeat of the same attempts.
- **Open questions**: each question that only the user can answer.
- **Pointers**: paths, the branch, PR and issue URLs, and the commands to build and test.
- **Skills to use**: the skills and agents that the next session needs, by full name.

Do not copy content that a file, a commit, a PR, or an issue already holds. Give the path
or the URL. A copy goes out of date, and the reader cannot tell which version is correct.

Example of a next step:

- Bad: "Finish the cache work and fix the remaining test."
- Good: "Make `tests/cache/evict.test.ts` pass. It fails with `expected 3, received 4`
  at line 52, because `evictOldest()` in `src/cache/lru.ts` does not count the entry it
  adds. Run `pnpm test tests/cache/evict.test.ts` to see the failure."

## 3. Remove secrets

Read the document once for secrets and personal data: API keys, tokens, passwords,
connection strings, email addresses, customer data. Replace each one with a description
of where the reader can get it, such as "the token in `.env`, key `STRIPE_KEY`".

## 4. Save it outside the workspace

Save the document in the temporary folder of the operating system, not in the repo, so
that nobody commits it. Use `$TMPDIR` if it is set, and `/tmp` if it is not. On Windows,
use `%TEMP%`. Name the file `handoff-<short-task-name>-<YYYY-MM-DD>.md`.

## 5. Check, then report

- [ ] Each path in the document exists. Run `ls` on each one.
- [ ] Each "it", "this", and "the bug" names its subject in the same sentence.
- [ ] The next step names a file and a command.
- [ ] Each claim in State has a label, and each verified claim has its evidence.
- [ ] The document has no secret.

Print the full path of the file. Then print one line that the user can paste into a new
session, such as: `Read <full path> and continue from "Next step".`
