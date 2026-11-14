---
name: interview
description: >
  Interview the user about a plan, a design, or a decision until each open decision is
  settled, before any plan or code. Use when the user says "grill me", "interview me",
  "stress-test this", or "poke holes in this", or asks if a plan is ready. Not for a
  clear task that is ready to do, and not for a session where no user can answer.
---

# Interview

Interview the user until you and the user agree on what to build and on what not to
build. You find the facts. The user makes the decisions. In this skill, you change no
file and you start no work.

## 0. Check that a user can answer

This skill needs a user who answers in this session. If you run as a subagent, in CI, in
a loop, or in a non-interactive run, do not start the interview. Report the open
decisions as a blocker and stop.

## 1. State what you know

Write one sentence that says what you think the user wants. Then list which of these five
items you cannot fill from the conversation:

- **User**: who the result is for.
- **Reason**: why the user wants it now.
- **Success**: what a person can observe when it works.
- **Constraint**: the limit that the result must not break (time, cost, compatibility).
- **Out of scope**: what the user does not want built.

Show the sentence and the list to the user before the first question.

## 2. Separate facts from decisions

List every open point. Sort each one:

- A **fact** has an answer in the environment: the repo, a config file, the output of a
  command, the docs. Find it yourself. Read the file, run the command, or start a
  subagent for a long search. Never ask the user for a fact that you can look up.
- A **decision** has no answer until the user gives one. Put each decision to the user.

Gate: before you ask a question, you can say why no file and no command can answer it.

Example. The user says "add caching to the product page".

- Fact: "Does the repo have a cache client?" Search the repo. Do not ask.
- Decision: "Can a customer see a price that is five minutes old?" Only the user knows.

## 3. Ask in rounds

Some decisions depend on other decisions. The **frontier** is the set of decisions that
depend on nothing that is still open. In each round:

1. Take the decisions on the frontier. If there are more than four, take the four that
   the most other decisions depend on.
2. Number each question. Give your recommended answer and one reason with it.
3. Word each question so that "yes" accepts your recommendation.
4. Stop and wait for the answers. Do not answer for the user.

Use this format:

```
Q1. <question title>: <the question, with the options if there are options>
Recommended: <your answer>, because <one reason>.
```

A recommendation that the user can reject is faster than an open question. The user
corrects a wrong guess more easily than the user writes an answer from nothing.

After each round, record the answers, look up each fact that the answers make necessary,
and find the new frontier. A question that depends on an open question belongs to a later
round.

## 4. Test each answer

An answer that names a convention is not a decision. Watch for answers such as
"scalable", "clean", "the standard way", "best practice", and "what most apps do". For
each one, ask for the specific result:

- "Scalable to how many requests each second, and by what date?"
- "If you did not have to explain this choice to anyone, what do you want?"

An answer that gives the decision back to you ("whatever you think") is also not a
decision. Give two concrete options and ask the user to select one.

## 5. Restate

When the frontier is empty, write the result. Use the user's own words where you can.

```
What I think you want:

- Outcome: <one line>
- User: <one line>
- Reason: <one line>
- Success: <one line that a person can observe>
- Constraint: <one line>
- Out of scope: <one line>

Decisions:
1. <decision>: <answer>
2. ...

Still open: <each point that the user chose to leave open, or "nothing">

Is this correct? Answer yes, or tell me which line to change.
```

Always fill "Out of scope". Many disagreements are about what the work does not include.

## 6. Get an explicit yes

The interview is complete only when the user confirms the restatement. These replies are
not a yes:

- "Sounds good" or "sure, go ahead": ask "Is there a line that you want to change?"
- "Whatever you think is best": the user did not decide. Go back to step 4.
- No answer to the restatement, and then a new request: ask if the restatement is correct.

If the user corrects a line, change it and show the full restatement again.

## 7. Stop

After the yes, do these two things, and then end your turn:

1. Show the confirmed restatement one more time, as the final record.
2. Tell the user the possible next steps: plan mode for an implementation plan, or
   `/team:tickets` to split the work into tickets.

Do not write a plan, a file, or code in the same turn. The user selects the next step.

## Circuit breaker

Stop and say so when one of these conditions is true:

- Five rounds are complete and the frontier is not empty.
- Two rounds in a row end with more open decisions than they started with.

Tell the user the number of rounds, the decisions that stay open, and what you think is
missing. Ask if the user wants to continue, to make the scope smaller, or to stop.

## Final self-check

- [ ] You asked no question that a file or a command can answer.
- [ ] Each question had a recommended answer and a reason.
- [ ] The restatement has all six lines, and "Out of scope" is not empty.
- [ ] The user gave an explicit yes to the restatement.
- [ ] You changed no file and started no work.
