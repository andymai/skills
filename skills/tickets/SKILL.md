---
name: tickets
description: Split a plan, a spec, or the current conversation into tickets. Each ticket is a vertical slice and names the tickets that block it.
argument-hint: "[path, issue number, or URL of the plan or spec]"
disable-model-invocation: true
---

# Tickets

Split the work into tickets that an engineer or an agent can do one at a time. Each
ticket is a **vertical slice**: a narrow change that goes through every layer and that
someone can verify by itself. Each ticket names the tickets that **block** it.

The source of the work, if the user gave one: $ARGUMENTS

## 1. Get the source

If the line above names a file, an issue, or a URL, read all of it, with its comments.
If the line is empty, use the plan in the current conversation.

Gate: you can state the goal and what is out of scope in two sentences. If you cannot,
stop. Tell the user that the work is not ready to split, and that `/team:interview` settles
the open decisions.

## 2. Read the code

Read the code that the work changes. Find the layers that a feature goes through in this
repo (for example: schema, API, UI, tests) by reading one existing feature from end to
end.

Look for a **prefactor**: a change that makes the work easy and changes no behavior.
First make the change easy, then make the easy change. A prefactor is its own ticket,
and it blocks the tickets that need it.

## 3. Find where the tickets go

Use the first rule that applies:

1. The user's instructions name a tracker or a folder.
2. The project's `CLAUDE.md` or `AGENTS.md` names a tracker and its conventions (labels,
   a template, a project).
3. Ask the user: a tracker, or local files.

Do not publish to a tracker that neither the user nor the project named. For local files,
use the folder that the user names. If the user names none, use
`.scratch/<feature-name>/`, and run `git check-ignore .scratch` to tell the user if git
ignores the folder.

## 4. Draft the slices

Rules for each ticket:

- It makes one behavior work from end to end, through every layer that the behavior
  needs. It is not one layer of many behaviors.
- Someone can verify it by itself when it is complete: run it, see it, or test it.
- It fits in one work session for one engineer or one agent.
- It lists its **blocked by** tickets: the tickets that must be complete before it
  starts. A ticket with no blocker can start immediately.

Example. The work is "let a user export their orders as CSV".

- Bad (horizontal): "1. Add the export tables. 2. Write the export API. 3. Build the
  export UI. 4. Write the tests." Nobody can verify ticket 1, 2, or 3 by itself.
- Good (vertical): "1. Export the order ID and the total for one user, from a button on
  the orders page, with a test. 2. Add the line items to the file (blocked by 1).
  3. Send the file by email when the export has more than 10,000 rows (blocked by 1)."

**Exception: a wide refactor.** One mechanical change (rename a column, change a shared
type) can break call sites in all of the codebase, so no vertical slice can pass CI. Do
not force it into slices. Use three stages:

1. **Expand**: add the new form next to the old form. Nothing breaks.
2. **Migrate**: move the call sites in batches (one package or one folder in each
   ticket). Each batch is blocked by the expand ticket. CI passes after each batch,
   because the old form still exists.
3. **Contract**: delete the old form. This ticket is blocked by every migrate ticket.

## 5. Show the breakdown and get approval

Show a numbered list. For each ticket, give its title, its blockers, and the behavior
that works when it is complete. Then ask the user these three questions:

1. Is each ticket the right size, or is one too large or too small?
2. Is each blocker correct? Does a ticket wait for a ticket that it does not need?
3. Do you want to merge two tickets or to split one?

Change the list and show it again until the user approves it. Gate: do not write a
ticket until the user approves the list.

## 6. Write the tickets

Use this template for each ticket:

```
# <title that states the change>

## What to build
<The behavior that works when the ticket is complete, as the user of the product sees
it. Not a list of changes for each layer.>

## Acceptance criteria
- [ ] <a result that a person can check with a command or an action>
- [ ] ...

## Blocked by
<each blocking ticket, or "Nothing. This ticket can start immediately.">

## Out of scope
<what this ticket does not do, and which ticket does it>
```

Rules for the text:

- Write each acceptance criterion as a result that someone can check. "The export works"
  is not a criterion. "A file with 3 orders has 4 lines: the header and one line for each
  order" is a criterion.
- Do not give file paths or code. They go out of date before someone starts the ticket.
  The exception is a short snippet that states a decision more exactly than prose: a
  schema, a type, or a state table.
- Use the project's own words for its domain objects.

**Local files**: write one file for each ticket, named `<NN>-<short-title>.md`. Number
from `01` in dependency order, with the blockers first. Before you write, list the
folder. If it has ticket files from an earlier run, do not overwrite them. Ask the user
if you must replace that set or use a new folder.

**A tracker**: a ticket is prose that other people read. Before you publish, invoke the
`team:outward-writing` skill with the Skill tool, and follow it for the text of each
ticket. Show the full text of each ticket to the user before you publish it. Publish in dependency order, with the blockers first, so that each ticket can
give the real ID of its blockers. If the tracker has a native "blocked by" link, use it.
If the source was an issue, link each ticket to it as the parent. Do not close or change
the parent issue.

## 7. Report

- Each ticket with its ID or its path, in dependency order.
- The tickets that can start now (no blocker).
- Anything from the source that no ticket covers, and why.

## Final self-check

- [ ] Each ticket goes through every layer that its behavior needs, or it is a stage of a
  wide refactor.
- [ ] Each acceptance criterion is a result that someone can check.
- [ ] No ticket waits for itself through a chain of blockers.
- [ ] Each requirement in the source is in a ticket, or the report says that it is not.
- [ ] The user approved the list before you wrote a ticket, and saw each ticket before
  you published it to a tracker.
