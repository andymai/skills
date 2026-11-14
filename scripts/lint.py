#!/usr/bin/env python3
"""Lint the plugin's agents, commands, skills, and manifests.

Usage: python3 -I scripts/lint.py [--root DIR] [--base GIT_REF]

Exit 0 when every check passes, and exit 1 otherwise. With --base, the lint
also fails when a shipped file changed since GIT_REF and the version in
.claude-plugin/plugin.json did not increase.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# https://code.claude.com/docs/en/sub-agents (frontmatter reference).
AGENT_COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}
AGENT_MODELS = {"opus", "sonnet", "haiku", "fable", "inherit"}
AGENT_REQUIRED = ("name", "description", "tools", "model", "color")
AGENT_KEYS = set(AGENT_REQUIRED) | {
    "disallowedTools", "skills", "effort", "maxTurns", "memory", "background",
    "isolation", "omitClaudeMd", "autoCompactWindow", "experimental",
}
# Claude Code ignores these keys when it loads an agent from a plugin.
AGENT_IGNORED_IN_PLUGIN = {"hooks", "mcpServers", "permissionMode", "initialPrompt"}
CORE_TOOLS = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"}

COMMAND_KEYS = {
    "description", "argument-hint", "arguments", "when_to_use",
    "disable-model-invocation", "user-invocable", "allowed-tools",
    "disallowed-tools", "model", "effort", "context", "agent",
}
SKILL_KEYS = COMMAND_KEYS | {
    "name", "paths", "hooks", "shell", "background", "license", "compatibility", "metadata",
}

# The Agent Skills specification limit. Claude Code cuts the listing at 1,536.
MAX_DESCRIPTION = 1024
MAX_SKILL_LINES = 500

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MUSTACHE = re.compile(r"\{\{\s*[A-Z][A-Z0-9_]*\s*\}\}")
PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
SHIPPED = re.compile(r"^(agents|commands|skills|hooks)/")
NOT_SHIPPED = re.compile(r"^skills/[^/]+/tests/")


class FrontmatterError(Exception):
    pass


def _scalar(raw, lineno):
    value = raw.strip()
    if not value:
        return ""
    if value[0] in "\"'":
        if len(value) < 2 or value[-1] != value[0]:
            raise FrontmatterError(f"line {lineno}: quote is not closed")
        inner = value[1:-1]
        unescaped = inner.replace("\\" + value[0], "") if value[0] == '"' else inner.replace("''", "")
        if value[0] in unescaped:
            raise FrontmatterError(f"line {lineno}: quote character inside a quoted value")
        return inner
    if value[0] in "{}]#,*&!%@`|>" or value.startswith(("- ", "? ")) or value in ("-", "?"):
        raise FrontmatterError(
            f"line {lineno}: value starts with {value[0]!r}; put the value in quotes"
        )
    if ": " in value or value.endswith(":"):
        raise FrontmatterError(
            f"line {lineno}: unquoted value contains a colon; put the value in quotes"
        )
    if " #" in value:
        raise FrontmatterError(
            f"line {lineno}: unquoted value contains ' #', which starts a YAML comment"
        )
    return value


def _flow_list(raw, lineno):
    inner = raw.strip()
    if not inner.endswith("]") or inner.count("[") != 1 or inner.count("]") != 1:
        raise FrontmatterError(
            f"line {lineno}: value starts with '[' but is not one flow list; put the value in quotes"
        )
    return [_scalar(item, lineno) for item in inner[1:-1].split(",") if item.strip()]


def parse_frontmatter(text):
    """Parse the YAML subset that this repo uses. Reject everything else.

    The strict subset is deliberate: a value that one YAML parser accepts and
    another rejects makes a skill disappear in some harnesses.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("file does not start with a '---' frontmatter line")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise FrontmatterError("frontmatter has no closing '---' line") from None
    data = {}
    i = 1
    while i < end:
        line = lines[i]
        lineno = i + 1
        if "\t" in line:
            raise FrontmatterError(f"line {lineno}: tab character in frontmatter")
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", line)
        if not match:
            raise FrontmatterError(f"line {lineno}: expected 'key: value'")
        key, rest = match.group(1), match.group(2)
        if rest and not rest.startswith(" "):
            raise FrontmatterError(f"line {lineno}: expected a space after the colon")
        if key in data:
            raise FrontmatterError(f"line {lineno}: duplicate key {key!r}")
        rest = rest.strip()
        block = []
        j = i + 1
        while j < end and (lines[j].startswith(" ") or not lines[j].strip()):
            block.append(lines[j])
            j += 1
        while block and not block[-1].strip():
            block.pop()
        if rest in (">", ">-", "|", "|-"):
            if not block:
                raise FrontmatterError(f"line {lineno}: block scalar {key!r} is empty")
            joiner = " " if rest.startswith(">") else "\n"
            data[key] = joiner.join(part.strip() for part in block).strip()
            i = j
        elif rest == "":
            items = [part.strip() for part in block if part.strip()]
            if not items or not all(item.startswith("- ") for item in items):
                raise FrontmatterError(
                    f"line {lineno}: {key!r} has no value; only a '- item' list can follow"
                )
            data[key] = [_scalar(item[2:], lineno) for item in items]
            i = j
        else:
            if block:
                raise FrontmatterError(
                    f"line {lineno}: unexpected indented line after {key!r}"
                )
            data[key] = _flow_list(rest, lineno) if rest.startswith("[") else _scalar(rest, lineno)
            i += 1
    return data, "\n".join(lines[end + 1:])


class Lint:
    def __init__(self, root):
        self.root = root
        self.errors = []
        self.checked = 0
        self.texts = {}
        self.agents = set()
        self.commands = set()
        self.skills = set()

    def fail(self, path, message):
        rel = path.relative_to(self.root) if isinstance(path, Path) else path
        self.errors.append(f"FAIL {rel}: {message}")

    def read(self, path):
        if path not in self.texts:
            try:
                self.texts[path] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as err:
                self.fail(path, f"cannot read the file as UTF-8: {err}")
                self.texts[path] = None
        return self.texts[path]

    def read_json_object(self, path):
        text = self.read(path)
        if text is None:
            return None
        try:
            data = json.loads(text)
        except ValueError as err:
            self.fail(path, f"cannot read the manifest: {err}")
            return None
        if not isinstance(data, dict):
            self.fail(path, "the manifest is not a JSON object")
            return None
        return data

    def load(self, path):
        self.checked += 1
        text = self.read(path)
        if text is None:
            return None
        try:
            return parse_frontmatter(text)
        except FrontmatterError as err:
            self.fail(path, f"frontmatter: {err}")
            return None

    def unknown_keys(self, path, data, allowed):
        for key in sorted(set(data) - allowed):
            self.fail(path, f"frontmatter key {key!r} is not a known key")

    def description(self, path, data):
        desc = data.get("description")
        if not isinstance(desc, str) or not desc.strip():
            self.fail(path, "frontmatter needs a non-empty 'description'")
        elif len(desc) > MAX_DESCRIPTION:
            self.fail(path, f"description is {len(desc)} characters; the limit is {MAX_DESCRIPTION}")

    def grants(self, path, data):
        tools = data.get("allowed-tools")
        if isinstance(tools, str):
            tools = [tool.strip() for tool in re.split(r"[,\s]+(?![^(]*\))", tools) if tool.strip()]
        for tool in tools or []:
            if tool in ("Bash", "Bash(*)", "Bash(:*)"):
                self.fail(
                    path,
                    f"allowed-tools grants {tool}, which approves every shell command; "
                    "grant a pattern such as \"Bash(gh *)\"",
                )

    def placeholders(self, path, body):
        for token in sorted(set(MUSTACHE.findall(body))):
            self.fail(
                path,
                f"{token} is not a placeholder that Claude Code replaces; use $ARGUMENTS",
            )

    def body(self, path, body):
        for ref in sorted(set(PLUGIN_ROOT_REF.findall(body))):
            target = ref.rstrip("./")
            if not (self.root / target).exists():
                self.fail(path, f"${{CLAUDE_PLUGIN_ROOT}}/{ref} does not exist in the repo")

    def lint_agents(self):
        for path in sorted((self.root / "agents").glob("*.md")):
            self.agents.add(path.stem)
            parsed = self.load(path)
            if parsed is None:
                continue
            data, body = parsed
            for key in AGENT_REQUIRED:
                if key not in data:
                    self.fail(path, f"frontmatter needs {key!r}")
            for key in sorted(AGENT_IGNORED_IN_PLUGIN & set(data)):
                self.fail(path, f"Claude Code ignores {key!r} for a plugin agent; remove it")
            self.unknown_keys(path, data, AGENT_KEYS | AGENT_IGNORED_IN_PLUGIN)
            self.description(path, data)
            if "name" in data and data["name"] != path.stem:
                self.fail(path, f"name {data['name']!r} does not match the file name {path.stem!r}")
            if not KEBAB.match(path.stem):
                self.fail(path, "file name is not kebab-case")
            color = data.get("color")
            if color is not None and (not isinstance(color, str) or color not in AGENT_COLORS):
                self.fail(path, f"color {color!r} is not valid; use one of {', '.join(sorted(AGENT_COLORS))}")
            model = data.get("model")
            if model is not None and (
                not isinstance(model, str)
                or (model not in AGENT_MODELS and not model.startswith("claude-"))
            ):
                self.fail(path, f"model {model!r} is not valid; use one of {', '.join(sorted(AGENT_MODELS))} or a full model ID")
            tools = data.get("tools")
            if isinstance(tools, str):
                tools = [tool.strip() for tool in tools.split(",") if tool.strip()]
            for tool in tools or []:
                if tool not in CORE_TOOLS and not tool.startswith("mcp__"):
                    self.fail(path, f"tool {tool!r} is not a core tool or an mcp__ tool")
            self.placeholders(path, body)
            self.body(path, body)

    def lint_commands(self):
        for path in sorted((self.root / "commands").glob("*.md")):
            self.commands.add(path.stem)
            parsed = self.load(path)
            if parsed is None:
                continue
            data, body = parsed
            self.unknown_keys(path, data, COMMAND_KEYS)
            self.description(path, data)
            self.grants(path, data)
            if not KEBAB.match(path.stem):
                self.fail(path, "file name is not kebab-case")
            self.placeholders(path, body)
            self.body(path, body)

    def lint_skills(self):
        skills_dir = self.root / "skills"
        if not skills_dir.is_dir():
            return
        for folder in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            path = folder / "SKILL.md"
            if not path.is_file():
                self.fail(folder, "skill folder has no SKILL.md")
                continue
            self.skills.add(folder.name)
            parsed = self.load(path)
            if parsed is None:
                continue
            data, body = parsed
            self.unknown_keys(path, data, SKILL_KEYS)
            self.description(path, data)
            self.grants(path, data)
            if data.get("name") != folder.name:
                self.fail(path, f"name {data.get('name')!r} does not match the folder name {folder.name!r}")
            if not KEBAB.match(folder.name):
                self.fail(path, "folder name is not kebab-case")
            count = len((self.read(path) or "").splitlines())
            if count > MAX_SKILL_LINES:
                self.fail(path, f"{count} lines; move reference material out to keep SKILL.md at {MAX_SKILL_LINES} lines or fewer")
            self.placeholders(path, body)
            self.body(path, body)
            # A reference file can name a banned token to explain it, so it gets
            # only the path check.
            for extra in sorted(folder.rglob("*.md")):
                if extra != path and "tests" not in extra.relative_to(folder).parts:
                    text = self.read(extra)
                    if text is not None:
                        self.body(extra, text)

    def plugin_name(self):
        manifest = self.root / ".claude-plugin" / "plugin.json"
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        name = data.get("name") if isinstance(data, dict) else None
        return name if isinstance(name, str) else None

    def lint_cross_references(self):
        name = self.plugin_name()
        if not name:
            return
        known = self.agents | self.commands | self.skills
        pattern = re.compile(r"(?<![\w-])/?" + re.escape(name) + r":([a-z][a-z0-9-]*)")
        files = [self.root / "README.md", self.root / "AGENTS.md"]
        for sub in ("agents", "commands", "skills"):
            files += sorted((self.root / sub).rglob("*.md"))
        for path in files:
            if not path.is_file() or "tests" in path.relative_to(self.root).parts:
                continue
            text = self.read(path)
            for target in sorted(set(pattern.findall(text or ""))):
                if target not in known:
                    self.fail(path, f"{name}:{target} names no agent, command, or skill in this plugin")

    def lint_readme(self):
        readme = self.root / "README.md"
        name = self.plugin_name()
        if not readme.is_file() or not name:
            return
        text = self.read(readme)
        if text is None:
            return
        for agent in sorted(self.agents):
            if f"**{agent}**" not in text:
                self.fail(readme, f"agent {agent!r} is not in the agent table")
        for skill in sorted(self.skills):
            if f"**{skill}**" not in text:
                self.fail(readme, f"skill {skill!r} is not in the skill table")
        for command in sorted(self.commands):
            if f"/{name}:{command}" not in text:
                self.fail(readme, f"command /{name}:{command} is not in the command table")

    def lint_manifests(self):
        plugin_path = self.root / ".claude-plugin" / "plugin.json"
        market_path = self.root / ".claude-plugin" / "marketplace.json"
        self.checked += 1
        plugin = self.read_json_object(plugin_path)
        if plugin is None:
            return None
        for key in ("name", "version", "description"):
            if not plugin.get(key):
                self.fail(plugin_path, f"manifest needs {key!r}")
        version = str(plugin.get("version", ""))
        if version and not SEMVER.match(version):
            self.fail(plugin_path, f"version {version!r} is not MAJOR.MINOR.PATCH")
        if market_path.is_file():
            self.checked += 1
            market = self.read_json_object(market_path)
            if market is None:
                return version
            listed = market.get("plugins", [])
            if not isinstance(listed, list) or not all(isinstance(e, dict) for e in listed):
                self.fail(market_path, "'plugins' is not a list of objects")
                return version
            entries = [e for e in listed if e.get("name") == plugin.get("name")]
            if not entries:
                self.fail(market_path, f"no plugin entry is named {plugin.get('name')!r}")
            for entry in entries:
                if "version" in entry and entry["version"] != version:
                    self.fail(market_path, f"entry version {entry['version']!r} is not the plugin.json version {version!r}")
        return version

    def lint_version_bump(self, base, version):
        def git(*args):
            return subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True, text=True, check=False,
            )

        merge_base = git("merge-base", base, "HEAD")
        if merge_base.returncode != 0:
            self.fail("--base", f"git cannot find a merge base with {base!r}: {merge_base.stderr.strip()}")
            return
        start = merge_base.stdout.strip()
        # -z and --no-renames: a rename out of a shipped folder must show the
        # old path, and git must not quote a path with a non-ASCII character.
        changed = set(git("diff", "--name-only", "--no-renames", "-z", start).stdout.split("\0"))
        changed |= set(git("ls-files", "-z", "--others", "--exclude-standard").stdout.split("\0"))
        shipped = sorted(p for p in changed if SHIPPED.match(p) and not NOT_SHIPPED.match(p))
        if not shipped:
            return
        new_match = SEMVER.match(version or "")
        if not new_match:
            return
        new_tuple = tuple(map(int, new_match.groups()))
        # The tip of the base can have a higher version than the merge base,
        # when another branch merged first. The new version must pass both.
        for ref, label in ((start, f"the merge base with {base}"), (base, base)):
            old = git("show", f"{ref}:.claude-plugin/plugin.json")
            try:
                data = json.loads(old.stdout)
            except ValueError:
                continue
            old_match = SEMVER.match(str(data.get("version", ""))) if isinstance(data, dict) else None
            if old_match and new_tuple <= tuple(map(int, old_match.groups())):
                self.fail(
                    ".claude-plugin/plugin.json",
                    f"version is {version} and {label} has {old_match.group(0)}, but {len(shipped)} shipped "
                    f"file(s) changed (first: {shipped[0]}). Increase the version, or no user gets the change",
                )
                return


def main():
    parser = argparse.ArgumentParser(description="Lint the plugin's components and manifests.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--base", help="git ref to compare with for the version check")
    args = parser.parse_args()
    lint = Lint(Path(args.root).resolve())
    lint.lint_agents()
    lint.lint_commands()
    lint.lint_skills()
    lint.lint_cross_references()
    lint.lint_readme()
    version = lint.lint_manifests()
    if args.base:
        lint.lint_version_bump(args.base, version)
    if lint.errors:
        print("\n".join(lint.errors))
        print(f"FAIL: {len(lint.errors)} problem(s) in {lint.checked} files")
        return 1
    print(f"PASS: {lint.checked} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
