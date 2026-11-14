<div align="center">

# Skills

A Claude Code plugin named `team`, with skills, subagents, slash commands, scripts, and templates. The subagents (engineer, reviewer, debugger, and more) combine into workflow recipes.

[Agents](#agents) · [Workflow Skills](#workflow-skills) · [Workflow Recipes](#workflow-recipes) · [Quick Start](#quick-start)

</div>

---

This repo is a [Claude Code plugin](https://code.claude.com/docs/en/plugins) with agent definitions, slash commands, and workflow skills. It is also its own marketplace, named `andymai`. When you install the plugin, Claude Code registers its agents in every project that you open.

## Quick Start

You need [Claude Code](https://docs.claude.com/en/docs/claude-code). In any session, run:

```
/plugin marketplace add andymai/skills
/plugin install team@andymai
```

To get later changes:

1. Refresh the catalog with `/plugin marketplace update andymai`.
2. From a shell, run `claude plugin update team@andymai`, or pick Update from the `/plugin` menu.

To remove everything, run `/plugin uninstall team`.

The plugin name is the namespace of each component. Commands and skills are `/team:commit`, `/team:shepherd-pr`, and so on. Agents are `team:engineer`, `team:reviewer`, and so on.

To work on the plugin itself, load a clone for one session with `claude --plugin-dir /path/to/skills`. An install copies the repo into the plugin cache, so edits to a clone do not reach the installed copy.

## Agents

| Agent              | Purpose                                                       | Model  | Features        |
| ------------------ | ------------------------------------------------------------- | ------ | --------------- |
| **engineer**       | Implement features and their tests to match the existing code patterns. Write the failing test first for a bug fix | Opus   |                 |
| **debugger**       | Investigate a bug: reproduce it, fix all layers, and use only real dependencies | Opus   |                 |
| **reviewer**       | Review code, and report only findings with a confidence of 60 or more | Opus   | read-only       |
| **researcher**     | Explore codebases, compare technologies, gather information   | Opus   | read-only       |
| **gap-finder**     | Verify that implementations match specs, and find missing requirements | Opus   | read-only       |
| **optimizer**      | Simplify and refactor recently changed code, with no change in behavior | Sonnet |                 |

For planning, use plan mode or Claude Code's built-in Plan agent. For a security review, use the built-in `/security-review`.

## Scope

By design, this plugin does not:

- **Replace or install Claude Code.** It needs Claude Code installed and logged in. This plugin only adds agents, slash commands, and skills on top of it.
- **Provide a runtime orchestration framework.** The agents are static markdown definitions that Claude Code reads. There is no daemon, scheduler, or message bus between agents.
- **Make workflow recipes executable.** The recipes under [Workflow Recipes](#workflow-recipes) suggest an order in which to invoke the agents. They are not automated pipelines that you can run with one command.
- **Bootstrap new projects.** The plugin adds agents and commands for existing projects. It does not scaffold repos, generate boilerplate code, or configure CI. The **obsidian-project** skill writes planning notes in an Obsidian vault, not code.
- **Work outside Claude Code.** The agent and slash-command formats are specific to the subagent protocol of Claude Code. Other LLM tools cannot use them without changes.

## Workflow Recipes

**Bug fix**:
```
debugger → engineer → reviewer
```

**New feature** (after plan mode):
```
engineer → gap-finder → reviewer
```

**Cleanup after a change**:
```
optimizer → reviewer
```

**Research before a decision**:
```
researcher (standalone)
```

Each agent works on its own and returns results. Claude Code decides which agent to invoke next.

## Workflow Skills

These [Agent Skills](https://code.claude.com/docs/en/skills) are not specific to one stack. After you install the plugin, every project can use them. Like all skills, they load in steps: only the `description` stays in context until the skill triggers.

| Skill            | Triggers on                                                   | What it does |
| ---------------- | ------------------------------------------------------------- | ------------ |
| **shepherd-pr**  | "shepherd the PR", "drive this PR to green", "clean up the PR" | Runs an autonomous loop on the PR of the current branch. It resolves review comments, fixes check-run findings (including neutral-status reviewers that the CI rollup hides), and waits for CI to pass. Then it reassigns the PR and reports. It works in any repo: it detects Graphite or plain git and gets the GitHub login at runtime |
| **outward-writing** | the deliverable is prose another person will read: a design doc, proposal, wiki page, Slack message, PR body or reply, review reply, ticket, email | You collect every fact with a source, write the draft in ASD-STE100 Simplified Technical English, fact-check it sentence by sentence, and run `check.py`. You publish nothing until the user sees the draft. It needs no external CLI |
| **obsidian-project** | "start a project in my vault", "set up project docs in Obsidian" | Creates one folder in an Obsidian vault with five linked notes: the overview, PRD, architecture, research, and tasks. It adds the project to the vault's index. It fills a section only from what you said or what it read, and the other sections keep a hidden prompt. A layout in the vault's own CLAUDE.md wins over the templates |
| **interview** | "grill me", "interview me", "stress-test this plan" | Interviews you in rounds until each open decision is settled. It looks up the facts itself and asks you only for decisions, each with a recommended answer. It restates the result and stops when you confirm it. It writes no plan and no code |
| **agent-docs** | you create, change, or review a skill, a subagent, a command, or a CLAUDE.md | Gives the authoring rules for a document that an agent follows: write for the weakest executor, write the description as a trigger, keep one source for each fact. Its reference file has the Claude Code frontmatter keys, argument tokens, and limits |
| **handoff** | you type `/team:handoff` | Writes a handoff document outside the repo, so that a new session can continue the work. It labels each claim as verified, inferred, or assumed, and it gives one exact next step |
| **retrospective** | you type `/team:retrospective` | Reviews a session and proposes changes to the agent's environment. Each proposal quotes the moment in the session that shows the cost. A mechanical rule becomes an automated check, not a line in a rules file |
| **tickets** | you type `/team:tickets` | Splits a plan or a spec into tickets. Each ticket is a vertical slice with acceptance criteria and the tickets that block it. It writes local files, or it publishes to the tracker that you or the project name |

## Slash Commands

| Command                     | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `/team:audit-claudemd`      | Audit or bootstrap the project's CLAUDE.md against observed conventions |
| `/team:branch`              | Create a branch with `<type>/<kebab-description>` naming      |
| `/team:check`               | Run the project's local quality gate (auto-detected)          |
| `/team:commit`              | Create a conventional commit from working tree changes        |
| `/team:contribution-report` | GitHub contribution summaries for performance reviews         |
| `/team:pr-description`      | Generate PR title and description from branch changes         |
| `/team:upgrade-dep`         | Upgrade a dependency and fix breaking changes                 |
| `/team:worktree`            | Set up a git worktree under `.worktrees/` for parallel work   |

Claude can also start a command on its own when your request matches the command's description. The exception is `/team:contribution-report`, which runs only when you type it, because it creates a GitHub repo and uploads to it.

## Scripts

`skills/outward-writing/scripts/check.py` ships with the **outward-writing** skill, which reaches it through `${CLAUDE_PLUGIN_ROOT}`. It fails a draft on em or en dashes outside code and quotes. It also fails a sentence over 25 words and a paragraph over 6 sentences. It warns on the present perfect, "-ing" verbs, possible passives, and two verbs for one action, and it reports the word count.

## Credits

Five skills adapt ideas from two MIT-licensed projects. The text in this repo is new. [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) has the license notices.

- **interview**: the decision rounds come from `grilling` in [mattpocock/skills](https://github.com/mattpocock/skills). The restatement and the explicit confirmation come from `interview-me` in [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills).
- **agent-docs**, **handoff**, **retrospective**, **tickets**: from `writing-for-agents`, `handoff`, `retro`, and `to-tickets` in [mattpocock/skills](https://github.com/mattpocock/skills).

For Obsidian syntax, Bases, Canvas, and the Obsidian CLI, install the official [obsidianmd/obsidian-skills](https://github.com/obsidianmd/obsidian-skills) plugin. The **obsidian-project** skill uses its skills when they are present.

## Contributing

To add or upgrade an agent, read [AGENTS.md](AGENTS.md), the playbook for agent authors. It covers the frontmatter schema, model selection, and the color palette. It also states two rules:

- The **generalization rule**: agents run in every repo you touch, so each rule must be portable.
- The **weakest-executor rule**: prompts must carry the discipline (evidence rules, hard gates, self-checks), so smaller models and junior engineers also succeed with them.

Run these gates before you open a PR. CI runs the same four:

```
python3 -I scripts/lint.py --base origin/main
python3 -I scripts/tests/test_lint.py
skills/outward-writing/tests/run.sh
claude plugin validate . --strict
```

The lint checks the frontmatter, the names, the cross-references, and the README tables. It also fails when a shipped file changes and the version in `.claude-plugin/plugin.json` stays the same.

The cases under `evals/` test that each skill starts on a request that it owns and stays quiet on a nearby request. Each run is a real model call on your account, so CI does not run them. Run them after you change a skill's `description`:

```
claude plugin eval . --model sonnet --no-publish
```
