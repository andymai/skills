---
description: Create a conventional commit from working tree changes
argument-hint: "[--type=TYPE] [--scope=SCOPE] [--breaking] [--dry-run] [--bundle | --split] [--path=DIR]"
context: fork
model: haiku
background: false
---

Stage and commit working tree changes as a Conventional Commit.

You run in a subagent. You do not see the conversation, and you cannot ask the user a question. Use only the arguments, the repo, and the rules below. Your final message goes back to the session that started you, so put in it everything that the user must see.

## Arguments

The arguments for this run are: `$ARGUMENTS`

Before you run a command, write one line that names each flag in that text, such as `Flags: --split, --dry-run`, or `Flags: none`. Make each decision below from that line. A flag that is not in the line is not set.

The flags are `--type=TYPE`, `--scope=SCOPE`, `--breaking`, `--dry-run`, `--bundle`, `--split`, and `--path=DIR`.

- Bad: the arguments are `--split`, and you write "no flag was passed".
- Good: the arguments are `--split`, you write `Flags: --split`, and you make one commit for each group.

## Process

If `--path=DIR` is set, run each git command as `git -C DIR ...`. Otherwise, run git in the current directory.

Run `git status` and `git diff` (and `git diff --cached` for already-staged work) in parallel. Inspect what changed and classify each logical change.

If the working tree contains multiple unrelated changes:

- With `--bundle`, make one commit with all of them.
- With `--split`, make one commit for each group. Stage each group's files by name.
- With neither flag, commit nothing. Return the groups as a numbered list, with the files in each group, and end with: "Run /team:commit again with --bundle or --split."

Stage files by name — never `git add -A` or `git add .`. Skip files that look like secrets (`.env`, credentials, keys, tokens), large binaries, or build artifacts; warn if the user has staged them already.

Compose the message:

- **Type** (required): one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Pick from the diff, not the filename.
- **Scope** (optional): a short noun in parentheses — module, package, or area. Use scopes you've seen in recent `git log` for this repo when they fit.
- **Breaking changes**: append `!` after type/scope (`feat(api)!: …`) and add a `BREAKING CHANGE:` footer explaining the migration. Set when `--breaking` is passed or the diff removes/renames public surface.
- **Subject**: imperative mood, lowercase first letter, no trailing period, under 72 chars total including the prefix.
- **Body** (when non-trivial): wrap at 72 cols, focus on *why* and tradeoffs, not *what* — the diff shows what.
- **Footer** (optional): `Refs: #123`, `Closes #456`, `BREAKING CHANGE: …`.

Put the message in your final message. On `--dry-run`, stop here and commit nothing.

Run the commit with a HEREDOC so multi-line messages format correctly:

```
git commit -m "$(cat <<'EOF'
type(scope): subject

body

footer
EOF
)"
```

## On hook failure

If a pre-commit hook fails, surface the hook output, attempt the obvious fix (re-run linter/formatter, re-stage modified files), then create a **new** commit. Never use `--amend` (the original commit didn't happen — amending would rewrite the previous one) and never `--no-verify`.

## After commit

Run `git status` to confirm. Print the new commit hash and subject line.

If CLAUDE.md or a `.gitmessage` template specifies conventions, follow those over defaults.
