# AGENTS.md

A playbook for AI agents working on `andymai/skills` itself. CLAUDE.md (when present) is shared human+agent guidance; this file is agent-specific.

## At a glance

- **What this repo is**: a Claude Code plugin bundling agent definitions (`agents/*.md`), slash commands (`commands/*.md`), and workflow skills (`skills/*/SKILL.md`). It doubles as its own marketplace: `.claude-plugin/marketplace.json` lists one plugin, `team`, with `"source": "./"`.
- **Distribution model**: users install with `/plugin marketplace add andymai/skills` then `/plugin install team@andymai`. The marketplace name is `andymai`, because a user cannot add two marketplaces with the same name, and a generic name such as `skills` can collide. Claude Code auto-discovers `agents/`, `commands/`, and `skills/` at the plugin root, so adding a file is all it takes to ship it. Components are namespaced by the plugin name (`/team:commit`, `team:engineer`).
- **Everything here runs across every project the user touches.** Agents, commands, and skills must be portable: stack-agnostic and free of repo-specific assumptions.
- **Paths inside agent and skill bodies**: reference bundled files through `${CLAUDE_PLUGIN_ROOT}` (it resolves anywhere in agent and skill content), never through `~/.claude/...`. The install path is a versioned cache directory outside the repo, so a hardcoded path is never correct.
- **The hard rule**: agents must not encode project-specific conventions. Read the local project's `CLAUDE.md`/`AGENTS.md` and follow *that*.

## The Generalization Rule

Every agent here is loaded by every Claude session for every repo. So:

- Don't hardcode language-specific rules. `unwrap()` is a Rust concept; `any` is TS-specific. Say "no panics in library code if the project bans them" — let the project's docs supply the specifics.
- Don't hardcode tool names. `pnpm`, `cargo`, `just` don't all exist everywhere. Say "the project's check command" and detect it.
- Don't hardcode paths. `src/core/store/` makes sense in gridfinity; nowhere else.
- Do encode **meta-patterns**: "find the project's error-handling convention before writing", "discover where tests live before placing one", "prefer property-based testing where the project already uses it."

When you upgrade an agent, ask: *would this rule make sense in a brand-new repo with a different stack?* If no, generalize it.

## Write for the Weakest Executor

These agents run under the model that the user selected, which can be a smaller and faster one. Engineers at every experience level read their reports. The prompt must carry the discipline that a strong executor supplies on its own. Author every rule so that the least capable executor still succeeds.

The rules are in `skills/agent-docs/SKILL.md`, which also ships as the `team:agent-docs` skill. Read that file before you write or change an agent, a command, or a skill. It is the one source for these rules: procedures over judgment, hard gates, demanding completion criteria, evidence rules, anti-fabrication rules, permission to not know, worked examples, circuit breakers, untrusted input, and the final self-check.

Verbosity is acceptable here: agent bodies load only when the agent is invoked, and a rule that prevents one hallucinated API call pays for itself. Keep the *frontmatter description* lean (it's always in context); spend tokens freely in the body where they buy correctness.

## Frontmatter Schema

### Agents (`agents/*.md`)

```yaml
---
name: <kebab-case>              # required, matches filename without .md
description: <one paragraph>    # required, used by Claude to decide when to invoke
tools: <comma-separated>        # required, see allowed tools below
disallowedTools: <list>         # optional hard-deny — see caveat below before using
model: opus | sonnet | haiku    # required, see model selection below
color: <color name>             # required, see palette below
---
```

**Allowed tool names**: `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebSearch`, `WebFetch`. (Don't list tools the agent never uses — the description should make use of every listed tool.)

**Optional MCP tools**: an agent with `WebFetch` can also list `mcp__firecrawl__firecrawl_scrape`, `mcp__firecrawl__firecrawl_search`, `mcp__firecrawl__firecrawl_map`, `mcp__firecrawl__firecrawl_crawl`, and `mcp__firecrawl__firecrawl_check_crawl_status`. Claude Code drops a listed MCP tool that no configured server provides, so the agent still runs on its core tools. The prompt must say when to use each MCP tool, and it must not depend on them. Any other MCP tool needs the same two properties: a core-tool fallback, and prompt text that says when to use it.

**Read-only agents are enforced by omission, not `disallowedTools`.** The `tools:` list is an allowlist, so leaving out `Write`/`Edit` already makes an agent read-only. Don't add `disallowedTools: Write, Edit` on top — it's redundant. Reserve `disallowedTools` for blocking a tool that would otherwise be *inherited* when no `tools:` allowlist is set.

**Model selection**:
- `opus` — reasoning-heavy work: implementation, debugging, review, research, gap-finding.
- `sonnet` — pattern-following work where speed matters: optimization.
- `haiku` — short, deterministic transforms only (currently unused here).

**Color palette**. Claude Code accepts only `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, and `cyan`. The lint rejects any other value.
- `green`: building (engineer)
- `red`, `orange`: finding problems (reviewer, debugger)
- `cyan`, `blue`: refining and research (optimizer, researcher)
- `purple`: gap-finding (post-implementation verification)
- `yellow`, `pink`: free for new roles

Avoid duplicating colors across agents that the user might invoke in the same workflow.

**Keys that do nothing in a plugin agent**: Claude Code ignores `hooks`, `mcpServers`, `permissionMode`, and `initialPrompt` when it loads an agent from a plugin. The lint rejects them.

### Commands (`commands/*.md`)

```yaml
---
description: <one short line>             # required
argument-hint: "<flags and arguments>"    # required when the command takes arguments; keep the quotes
disable-model-invocation: true            # only for a user-only command, see below
---
```

Claude Code replaces `$ARGUMENTS` in the body with the text that the user types after the command name. It replaces no token in double braces. The lint rejects an upper-case name in double braces, such as the `RAW_PROMPT` form, in an agent, a command, or a `SKILL.md`. Document the supported flags in the body.

**Claude can start a command on its own.** Claude Code treats a command as a skill, so Claude can invoke a command when a request matches its `description`. Set `disable-model-invocation: true` when the command has an effect outside the repo that the user did not ask for by name. Then only the user can start it. Example: `contribution-report` creates a GitHub repo and uploads to it.

### Skills (`skills/*/SKILL.md`)

```yaml
---
name: <kebab-case>           # required, matches the folder name
description: <triggers>      # required, 1,024 characters or fewer
allowed-tools: [...]         # optional, see below
argument-hint: "<arguments>" # optional, for a skill that takes arguments; keep the quotes
disable-model-invocation: true   # only for a user-only skill, by the same rule as for a command
---
```

The rules for `description`, `allowed-tools`, and the size of `SKILL.md` are in `skills/agent-docs/SKILL.md` and in its reference file, `skills/agent-docs/reference/claude-code.md`. Two of them cause the most mistakes: `allowed-tools` grants tools and does not restrict them, and a `description` states triggers and not the procedure. The lint rejects a bare `Bash` grant.

## Session shapes

### Shape 1: Adding a new agent
1. Identify the *meta-pattern* you're encoding (not the specific repo it came from). Confirm it generalizes.
2. Create `agents/<name>.md` with frontmatter from the schema above.
3. Body structure: one-line role statement → core approach → 3-7 numbered steps or checklists → constraints → output guidance.
4. Match the prose style of existing agents (terse, second-person, action-oriented).
5. Update `README.md` agent table and any workflow recipes that reference the new agent.
6. Test it: start a session with `claude --plugin-dir <repo path>` and confirm the agent appears as `team:<name>`. Don't test through an installed copy; installing copies the repo into the plugin cache, so your edits won't be in it.

### Shape 2: Upgrading an existing agent
1. Read the agent in full first — don't patch what you haven't understood.
2. Add new sections *after* existing ones where possible; don't reorder unless the existing structure is broken.
3. Run `git diff agents/<name>.md` and re-read — agent prompts are load-bearing; a typo in the rules ships to every session.

### Shape 3: Adding a slash command
1. Decide if it's worth a command vs. an agent. Commands are good for short, parameterized operations the user runs often (commit, branch, worktree). Agents are good for open-ended reasoning that benefits from a system prompt.
2. Create `commands/<name>.md`. The body should document supported flags up front.
3. Read the arguments from `$ARGUMENTS`, and add an `argument-hint`.
4. Reference, don't duplicate, conventions documented elsewhere — link to the relevant AGENTS.md section.
5. Update the `README.md` slash-command table, writing the command with its `/team:` prefix.

### Shape 4: Adding a workflow skill
1. Decide skill vs. command. A skill has a folder, so it can ship scripts, templates, and reference files. A command is one file. Claude can start either one from its `description`, unless the frontmatter sets `disable-model-invocation: true`.
2. Create `skills/<name>/SKILL.md`. The `description` is the only part always in context, so spend it on trigger conditions, not on explaining the procedure.
3. Put long reference material in `skills/<name>/reference/*.md`. It loads only once the skill fires, so the body can be thorough without costing context.
4. Keep it portable. A skill ships to every project the user opens, so detect the project's tooling instead of assuming it.
5. Update the `README.md` Workflow Skills table.
6. For a skill that Claude can start, add two eval cases under `evals/`: one request that must start the skill, and one nearby request that must not. A skill with `disable-model-invocation: true` needs no eval case for its trigger.

### Shape 5: Repo hygiene / docs
1. README.md is the human-facing pitch; AGENTS.md is the agent playbook. Don't mix audiences.
2. Claude Code auto-discovers `agents/`, `commands/`, and `skills/` at the plugin root. New files ship automatically, with no manifest edit needed.
3. **Bump `version` in `.claude-plugin/plugin.json` on every change that should reach users.** `plugin.json` pins an explicit version, so `/plugin update` compares against it and reports "already at the latest version" for any commit that didn't bump it. An unbumped change ships to nobody. CI runs `scripts/lint.py --base`, which fails a PR that changes a file under `agents/`, `commands/`, or `skills/` and keeps the version.

## Decision frameworks

- **Add a new agent vs. extend an existing one?** Extend when the new capability is a refinement (engineer learns a new convention, reviewer learns a new checklist). New agent when the role is fundamentally different (debugger ≠ reviewer). Before adding one, check that a Claude Code built-in (plan mode, the Plan agent, `/security-review`) does not already do the job. Do not split one job across two agents: tests belong to the agent that writes the code, because a separate test agent that nobody calls leaves changes without tests.
- **Hardcoded rule vs. discovered rule?** If the rule is in *every* well-run project, hardcode it (e.g., "read CLAUDE.md before starting"). If the rule depends on the project's stack or style, the agent should *discover* it locally.
- **Read-only vs. write-capable agent?** Read-only (omit `Write`/`Edit` from `tools:`) for analysis agents (reviewer, gap-finder, researcher). Write-capable for execution agents (engineer, debugger, optimizer).

## Conventions

- **Cross-references carry the `team:` prefix.** When a command or agent tells the executor to *invoke* another component in this bundle, name it `team:reviewer` or `/team:check`, never bare. A bare name can resolve to an unrelated user-scoped component or to nothing at all. Descriptive prose about scope boundaries ("that's the reviewer's job") stays unprefixed, and Claude Code built-ins like `/plugin` and `/reload-plugins` are never prefixed. In a command or a skill, name the tool too: write "invoke the `team:check` skill with the Skill tool" or "start the `team:reviewer` agent with the Agent tool". A bare `/team:check` in prose is a label that the executor can read past. This rule does not apply to an agent body, because the agents here have neither tool.
- **Commits**: conventional commits (`feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `ci`, `build`, `perf`, `style`, `revert`). Scope is optional and short.
- **Branch naming**: `<type>/<kebab-description>` matching the commit type.
- **One feature per PR.** Large agent rewrites that touch unrelated agents should be split.
- **Never reply to or post PR comments.** Agents and commands must not post comments, reply to review threads, or resolve threads on a PR (`gh pr comment`, `gh api .../comments`, etc.). Address review feedback through commits and report the resolution back to the user; the user owns all PR conversation. The one exception is the `shepherd-pr` skill, which the user starts for that purpose. It replies and resolves threads by default. It holds each reply back when the project's rules or the user's instructions forbid replies or require a review first.

## Quality gates

Run the first four gates before you open a PR. CI (`.github/workflows/ci.yml`) runs the same four.

| Gate | Command | It fails when |
|---|---|---|
| Lint | `python3 -I scripts/lint.py --base origin/main` | Frontmatter is outside the strict YAML subset. A name, color, model, or tool is not valid. A skill or a command grants a bare `Bash`. A `${CLAUDE_PLUGIN_ROOT}` path does not exist. A `team:` reference names nothing. The README does not list a component. A shipped file changed and the version did not increase. |
| Lint tests | `python3 -I scripts/tests/test_lint.py` | A lint rule accepts a bad input. |
| Checker tests | `skills/outward-writing/tests/run.sh` | A `fail-*` draft passes, a `pass-*` draft fails, or an `expect` or `reject` marker in a draft does not match the checker's output. |
| Manifest | `claude plugin validate . --strict` | A manifest or a component file has a schema error or a warning. |
| Evals | `claude plugin eval . --model sonnet --no-publish` | A skill does not start on a request that it owns, or starts on a request that it does not own. |

- **Lint rules need tests.** When you add a rule to `scripts/lint.py`, add a test to `scripts/tests/test_lint.py` that fails without the rule.
- **Evals cost money.** Each run is a real model call on your account, so CI does not run them. Run them after a change to a skill's `description`, and before a release. Each case under `evals/` has a `prompt.md` and one or more files in `graders/`. Keep the graders to the `tool_used` type, which costs nothing.
- **Pin the model.** Pass `--model`, so that a model change does not look like a regression. The default is three runs for each case. One run is noise: do not act on it.

## When You're Stuck

Report blocking state explicitly: what completed, what's blocking, what was attempted, what's needed from the user. Don't loop on the same failing command.
