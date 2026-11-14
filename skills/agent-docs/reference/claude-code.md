# Claude Code mechanics for skills, subagents, and commands

These facts come from the Claude Code docs on 2026-11-14, with Claude Code 2.1.325. The
docs change. When a fact decides what you write, fetch the page and read it again:

- Skills and commands: https://code.claude.com/docs/en/skills
- Subagents: https://code.claude.com/docs/en/sub-agents
- Plugin evals: https://code.claude.com/docs/en/plugin-evals

## Skills (`skills/<name>/SKILL.md`)

| Key | Effect |
|---|---|
| `name` | The name of the skill. The default is the folder name. Keep them the same. |
| `description` | What the skill does and when to use it. Claude reads it to decide when to start the skill. |
| `when_to_use` | More trigger text. Claude Code adds it to the description in the listing. |
| `argument-hint` | The hint that the user sees after the command name, such as `"[issue-number]"`. |
| `disable-model-invocation` | `true` means that only the user can start the skill. Its description leaves the context. |
| `user-invocable` | `false` hides the skill from the `/` menu. Claude can still start it. |
| `allowed-tools` | Tools that Claude can use with no permission prompt during the turn that starts the skill. |
| `disallowed-tools` | Tools that Claude cannot use while the skill is active. |
| `model`, `effort` | Overrides for the rest of the turn. |
| `context: fork`, `agent` | Run the skill in a subagent of the given type. |
| `paths` | Globs that limit when Claude loads the skill by itself. |

Rules that authors get wrong:

- **`allowed-tools` grants. It does not restrict.** All other tools stay available. Never
  grant a bare `Bash`: it approves every shell command for the turn, with no check. Grant
  a pattern for each command that the skill runs: `Bash(gh *)`, or
  `Bash(${CLAUDE_SKILL_DIR}/scripts/render.sh *)` for a bundled script. To remove a tool, use `disallowed-tools`.
- **The listing has a limit.** Claude Code cuts the `description` plus `when_to_use` at
  1,536 characters. The Agent Skills specification allows 1,024 characters for
  `description`. Stay at 1,024 or fewer, and put the main use case first.
- **Keep `SKILL.md` at 500 lines or fewer.** Move reference material to other files in
  the skill folder.
- **Quote a value that has a colon, or that starts with `[`.** An unquoted
  `description: Run it: fast` is not valid YAML, and some tools then skip the skill with
  no error. An unquoted `argument-hint: [a] [b]` is not valid YAML, and an unquoted `[a]` is a list,
  not a string.
- **The skill body stays in the conversation** after it loads. Claude Code does not read
  the file again on later turns. An `allowed-tools` grant ends when the user sends the
  next message.

## Arguments and paths

Claude Code replaces these tokens in the body of a skill or a command:

| Token | Value |
|---|---|
| `$ARGUMENTS` | All the text that the user typed after the name. |
| `$ARGUMENTS[0]`, `$0`, `$1` | One argument by position. |
| `$name` | A named argument from the `arguments` list in the frontmatter. |
| `${CLAUDE_SKILL_DIR}` | The folder of the skill's `SKILL.md`. |
| `${CLAUDE_PLUGIN_ROOT}` | The install folder of the plugin. Plugin skills only. |
| `${CLAUDE_PLUGIN_DATA}` | A data folder that stays after a plugin update. Plugin skills only. |
| `${CLAUDE_PROJECT_DIR}` | The project root. |
| `${CLAUDE_SESSION_ID}` | The ID of the session. |

- Claude Code replaces no other token. A name in double braces, such as the
  `RAW_PROMPT` form that some templates use, stays in the text as written.
- If the body has no argument token, Claude Code adds `ARGUMENTS: <input>` at the end.
- Never write an absolute path to a bundled file. A plugin installs into a cache folder
  with a version in its path. Use `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_SKILL_DIR}`.

## Commands (`commands/<name>.md`)

- Claude Code treats a command as a skill. It accepts the same frontmatter, except
  `name` and `paths`. A command is one file, so it cannot ship scripts or references.
- **Claude can start a command by itself** when a request matches its `description`. To
  make a command user-only, set `disable-model-invocation: true`.

## Subagents (`agents/<name>.md`)

| Key | Effect |
|---|---|
| `name`, `description` | Required. Claude reads the description to decide when to delegate. |
| `tools` | An allowlist. An agent with no `Write` and no `Edit` in the list is read-only. With no `tools` key, the agent inherits every tool. |
| `disallowedTools` | Removes tools from the `tools` list, or from the inherited set when there is no `tools` list. |
| `model` | `opus`, `sonnet`, `haiku`, `fable`, `inherit`, or a full model ID. |
| `color` | `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, or `cyan`. No other value. |
| `skills` | Skills whose full content loads into the agent when it starts. |
| `effort`, `maxTurns`, `memory`, `isolation`, `background` | Optional run settings. |

- A plugin agent cannot use `hooks`, `mcpServers`, `permissionMode`, or `initialPrompt`.
  Claude Code ignores these keys when it loads an agent from a plugin.
- `tools` for an agent restricts. `allowed-tools` for a skill grants. Do not confuse them.
- A subagent starts with a new context. It does not see the caller's conversation. It
  sees its own prompt, the task message from the caller, the CLAUDE.md files, and a git
  status. The task message must carry every other fact that the subagent needs.

## Validate and test a plugin

| Command | Use |
|---|---|
| `claude plugin validate . --strict` | Checks the manifests and the component files. With `--strict`, a warning fails. It does not check agent colors or argument tokens. |
| `claude --plugin-dir <path>` | Loads a plugin from a folder for one session. Use it to test a change. An installed plugin is a copy, so an edit to the repo does not reach it. |
| `claude plugin eval .` | Runs the cases in `evals/`. Each run is a real model call on your account. |
| `claude plugin tag` | Makes a release tag after it checks that the manifests agree on the version. |

A plugin that sets `version` in `plugin.json` reaches users only when the version
changes. Without a `version`, a plugin from a git source uses the commit SHA as its
version, so each commit is a new version.

### An eval case that tests a trigger

A case is a folder in `evals/` with a `prompt.md` and one or more files in `graders/`.

`evals/<case>/prompt.md`:

```markdown
---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

<a request that a user types, with no skill name in it>
```

`evals/<case>/graders/skill-fired.md` passes when Claude starts the skill:

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?<skill-name>"'
---
```

For a request that must not start the skill, add `min: 0`, `max: 0`, and `arm: both` to
the grader. A `tool_used` grader costs nothing. An `llm` grader calls a judge model.

Run one case one time while you work on it:

```
claude plugin eval . --case <case> --runs 1 --ablation none --no-publish
```

The default is three runs for each case. One run is noise, so run three before you rely
on a result. Pass `--model`, so that a model change does not look like a regression.
