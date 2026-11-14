---
description: Upgrade a dependency and fix breaking changes
argument-hint: "<package[@version]> [--dry-run] [--breaking]"
---

Upgrade one dependency and fix every breaking change that the upgrade causes.

## Process

Parse from: $ARGUMENTS. It expects `package[@version]`, and supports these flags:

- `--dry-run`: do steps 1 to 4 and change nothing.
- `--breaking`: the user accepts a new major version. Without this flag, do not cross a major version without a question first: show the breaking changes from step 4, and ask before step 5.

If the user gives no version, the target is the newest version in the installed major version. With `--breaking`, the target is the newest version.

Work through the steps in order. Each gate is a precondition for the next step.

1. **Find the package manager and the installed version.** Detect the package manager from the manifest and the lockfile. Do not assume one. Read the installed version from the lockfile or from the package manager's list command, not from the version range in the manifest. *Gate: you can quote the line that shows the installed version.*
2. **List the usage sites.** Grep for every import and use of the package. *Gate: you have a list of `file:line` locations, or you can name the search patterns that found none.*
3. **Record a baseline.** Before you change anything, run the project's type check, its tests, and its build, each as a separate command. Find the three commands in the manifest's scripts, the `Makefile` or `justfile`, or the CI workflow. Do not run one combined gate, because a combined gate stops at its first failure and then you have no result for the later checks. If the project has no command for one of the three, say so in the report. Record the summary line of each run. A check that fails here already failed before the upgrade, so do not blame the upgrade for it later. *Gate: for each of the three checks, you have the summary line of its run, or the statement that the project has no such command.*
4. **Read the breaking changes from a source that you fetch in this session.** Fetch the changelog, the release notes, or the migration guide for each version between the installed version and the target version. Your memory of a changelog is a hypothesis, not a fact. Quote each breaking change with its URL. If you cannot find a changelog, say so, list the sources that you tried, and use the compiler and the tests as the evidence. For a major version bump, show the summary of breaking changes before you continue. *Gate: each breaking change in your list has a quote and a URL, or the report states that no changelog exists.*
5. **Upgrade.** Use the package manager's own command, so that the lockfile changes with the manifest. Never edit a lockfile by hand. *Gate: the lockfile shows the target version. If the project has no lockfile, the package manager's list command shows it.*
6. **Fix each usage site that a breaking change affects.** Read the file before you edit it. After each logical fix, run the fastest correctness signal (the type check or one targeted test) and read its output.
7. **Run the same commands as the baseline.** Compare the two results line by line. *Gate: each check that passed in the baseline passes now, or the report names the check that does not and why.*

Example of the evidence that step 4 needs:

- Bad: "v5 removed the `parse` callback API." (No source. This can be a memory of a different library.)
- Good: "v5.0.0 release notes (https://example.com/releases/v5.0.0): 'The callback form of `parse()` is removed. Use the promise form.' The repo uses the callback form at `src/io/load.ts:41` and `src/io/save.ts:17`."

## Circuit breaker

If the same failure stays after two fix attempts, stop. Do not try a third fix. Report what you observed, what you ruled out, and the exact error text. If the upgrade cannot work without a larger change, say so, and ask before you revert the upgrade.

## Output

Report these items:

- The package, the old version, and the new version.
- Each breaking change, with its quote and URL, and the files that you changed for it.
- The baseline results and the final results for types, tests, and build, with the summary line of each run.
- Anything that needs a manual review.

Label each status claim as **verified** (you ran a command and read its output), **inferred** (you read code that implies it), or **assumed**.

If `--dry-run`: report the breaking changes, the affected `file:line` locations, and a risk assessment. Do not modify anything.
