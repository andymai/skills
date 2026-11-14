#!/usr/bin/env python3
"""Tests for scripts/lint.py. Run: python3 -I scripts/tests/test_lint.py"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LINT = Path(__file__).resolve().parent.parent / "lint.py"

AGENT = """---
name: helper
description: Helps with a task. Use when the task needs help.
tools: Read, Grep
model: opus
color: green
---

You help.
"""

COMMAND = """---
description: Run the thing
argument-hint: "[--fast] <target>"
---

Parse from: $ARGUMENTS
"""

SKILL = """---
name: do-work
description: >
  Does the work. Use when the user asks for the work,
  or for a part of it.
allowed-tools: [Read, "Bash(gh *)"]
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/do-work/reference/rules.md`. Then invoke `demo:helper`.
"""

README = "# Demo\n\n**helper** agent, **do-work** skill, `/demo:run` command.\n"


def make_plugin(root, version="1.0.0"):
    files = {
        ".claude-plugin/plugin.json": json.dumps(
            {"name": "demo", "version": version, "description": "A demo plugin."}
        ),
        ".claude-plugin/marketplace.json": json.dumps(
            {"name": "demo-market", "plugins": [{"name": "demo", "source": "./"}]}
        ),
        "agents/helper.md": AGENT,
        "commands/run.md": COMMAND,
        "skills/do-work/SKILL.md": SKILL,
        "skills/do-work/reference/rules.md": "# Rules\n",
        "README.md": README,
    }
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run_lint(root, *args):
    result = subprocess.run(
        [sys.executable, "-I", str(LINT), "--root", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout + result.stderr


def edit(root, rel, old, new):
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (rel, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def git(root, *args):
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, check=True,
    )


class LintTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_plugin(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def assert_fails(self, expected):
        code, out = run_lint(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn(expected, out)

    def test_valid_plugin_passes(self):
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS: 5 files", out)

    def test_invalid_agent_color(self):
        edit(self.root, "agents/helper.md", "color: green", "color: brightRed")
        self.assert_fails("color 'brightRed' is not valid")

    def test_agent_name_must_match_file(self):
        edit(self.root, "agents/helper.md", "name: helper", "name: assistant")
        self.assert_fails("does not match the file name 'helper'")

    def test_agent_missing_required_key(self):
        edit(self.root, "agents/helper.md", "model: opus\n", "")
        self.assert_fails("frontmatter needs 'model'")

    def test_agent_key_ignored_in_plugin(self):
        edit(self.root, "agents/helper.md", "color: green", "color: green\npermissionMode: plan")
        self.assert_fails("ignores 'permissionMode' for a plugin agent")

    def test_initial_prompt_is_ignored_in_plugin(self):
        edit(self.root, "agents/helper.md", "color: green", "color: green\ninitialPrompt: Start with the README.")
        self.assert_fails("ignores 'initialPrompt' for a plugin agent")

    def test_documented_optional_keys_are_allowed(self):
        edit(self.root, "agents/helper.md", "color: green", "color: green\nmaxTurns: 20\neffort: high")
        edit(self.root, "skills/do-work/SKILL.md", "name: do-work", "name: do-work\ncontext: fork\nbackground: false")
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)

    def test_agent_unknown_tool(self):
        edit(self.root, "agents/helper.md", "tools: Read, Grep", "tools: Read, Grpe")
        self.assert_fails("tool 'Grpe' is not a core tool")

    def test_agent_mcp_tool_is_allowed(self):
        edit(self.root, "agents/helper.md", "tools: Read, Grep", "tools: Read, mcp__x__search")
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)

    def test_mustache_placeholder_in_command(self):
        edit(self.root, "commands/run.md", "$ARGUMENTS", "{{RAW_PROMPT}}")
        self.assert_fails("{{RAW_PROMPT}} is not a placeholder")

    def test_unquoted_colon_in_description(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run it: fast")
        self.assert_fails("unquoted value contains a colon")

    def test_unquoted_argument_hint_with_two_lists(self):
        edit(self.root, "commands/run.md", '"[--fast] <target>"', "[--fast] [--slow]")
        self.assert_fails("is not one flow list")

    def test_unknown_frontmatter_key(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run the thing\nargs-hint: x")
        self.assert_fails("frontmatter key 'args-hint' is not a known key")

    def test_tab_in_frontmatter(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run\tthe thing")
        self.assert_fails("tab character in frontmatter")

    def test_duplicate_key(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run the thing\ndescription: Again")
        self.assert_fails("duplicate key 'description'")

    def test_unquoted_value_with_comment_marker(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run the thing #1")
        self.assert_fails("which starts a YAML comment")

    def test_value_that_starts_with_comment_marker(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: #1 runner")
        self.assert_fails("value starts with '#'")

    def test_value_that_starts_with_list_marker(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: - run it")
        self.assert_fails("value starts with '-'")

    def test_value_that_starts_with_special_character(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: *run it")
        self.assert_fails("value starts with '*'")

    def test_unclosed_quote(self):
        edit(self.root, "commands/run.md", "description: Run the thing", 'description: "Run the thing')
        self.assert_fails("quote is not closed")

    def test_quote_inside_quoted_value(self):
        edit(self.root, "commands/run.md", "description: Run the thing", 'description: "Run" the "thing"')
        self.assert_fails("quote character inside a quoted value")

    def test_escaped_quote_inside_quoted_value_is_allowed(self):
        edit(self.root, "commands/run.md", "description: Run the thing", 'description: "Run the \\"thing\\""')
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)

    def test_no_space_after_colon(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description:Run the thing")
        self.assert_fails("expected a space after the colon")

    def test_line_that_is_not_a_key(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run the thing\njust some words")
        self.assert_fails("expected 'key: value'")

    def test_indented_line_after_scalar(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run the thing\n  and more")
        self.assert_fails("unexpected indented line after 'description'")

    def test_key_with_no_value(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description:")
        self.assert_fails("'description' has no value")

    def test_empty_block_scalar(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: >")
        self.assert_fails("block scalar 'description' is empty")

    def test_block_list_is_parsed(self):
        edit(self.root, "skills/do-work/SKILL.md", 'allowed-tools: [Read, "Bash(gh *)"]', 'allowed-tools:\n  - Read\n  - "Bash(gh *)"')
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)

    def test_bare_bash_grant_in_skill(self):
        edit(self.root, "skills/do-work/SKILL.md", 'allowed-tools: [Read, "Bash(gh *)"]', "allowed-tools: [Read, Bash]")
        self.assert_fails("allowed-tools grants Bash, which approves every shell command")

    def test_bare_bash_grant_as_string_in_command(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run the thing\nallowed-tools: Read, Bash(*)")
        self.assert_fails("allowed-tools grants Bash(*)")

    def test_bash_pattern_grant_as_string_is_allowed(self):
        edit(self.root, "commands/run.md", "description: Run the thing", "description: Run the thing\nallowed-tools: Read, Bash(git add *), Bash(gh *)")
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)

    def test_missing_frontmatter(self):
        (self.root / "commands/run.md").write_text("Parse from: $ARGUMENTS\n", encoding="utf-8")
        self.assert_fails("does not start with a '---' frontmatter line")

    def test_frontmatter_without_closing_line(self):
        (self.root / "commands/run.md").write_text("---\ndescription: Run the thing\n", encoding="utf-8")
        self.assert_fails("no closing '---' line")

    def test_empty_description(self):
        edit(self.root, "commands/run.md", "description: Run the thing", 'description: ""')
        self.assert_fails("needs a non-empty 'description'")

    def test_command_file_name_must_be_kebab_case(self):
        (self.root / "commands/run.md").rename(self.root / "commands/Run_It.md")
        edit(self.root, "README.md", "`/demo:run` command", "`/demo:Run_It` command")
        self.assert_fails("commands/Run_It.md: file name is not kebab-case")

    def test_agent_file_name_must_be_kebab_case(self):
        (self.root / "agents/helper.md").rename(self.root / "agents/Helper_Agent.md")
        edit(self.root, "agents/Helper_Agent.md", "name: helper", "name: Helper_Agent")
        edit(self.root, "README.md", "**helper** agent", "**Helper_Agent** agent")
        edit(self.root, "skills/do-work/SKILL.md", " Then invoke `demo:helper`.", "")
        self.assert_fails("agents/Helper_Agent.md: file name is not kebab-case")

    def test_skill_folder_must_be_kebab_case(self):
        (self.root / "skills/do-work").rename(self.root / "skills/Do_Work")
        edit(self.root, "skills/Do_Work/SKILL.md", "name: do-work", "name: Do_Work")
        edit(self.root, "skills/Do_Work/SKILL.md", "skills/do-work/reference", "skills/Do_Work/reference")
        edit(self.root, "README.md", "**do-work** skill", "**Do_Work** skill")
        self.assert_fails("folder name is not kebab-case")

    def test_invalid_agent_model(self):
        edit(self.root, "agents/helper.md", "model: opus", "model: gpt-9")
        self.assert_fails("model 'gpt-9' is not valid")

    def test_full_model_id_is_allowed(self):
        edit(self.root, "agents/helper.md", "model: opus", "model: claude-opus-5-5")
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)

    def test_list_value_for_color_fails_without_a_crash(self):
        edit(self.root, "agents/helper.md", "color: green", "color: [green]")
        code, out = run_lint(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("is not valid", out)
        self.assertNotIn("Traceback", out)

    def test_list_value_for_model_fails_without_a_crash(self):
        edit(self.root, "agents/helper.md", "model: opus", "model:\n  - opus")
        code, out = run_lint(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("is not valid", out)
        self.assertNotIn("Traceback", out)

    def test_file_that_is_not_utf8_fails_without_a_crash(self):
        (self.root / "agents/helper.md").write_bytes(AGENT.encode("utf-8") + b"\xff\xfe\n")
        code, out = run_lint(self.root)
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("cannot read the file as UTF-8"), 1, out)
        self.assertIn("FAIL: 1 problem(s)", out)
        self.assertNotIn("Traceback", out)

    def test_plugin_manifest_that_is_not_an_object(self):
        (self.root / ".claude-plugin/plugin.json").write_text("[]", encoding="utf-8")
        code, out = run_lint(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("the manifest is not a JSON object", out)
        self.assertNotIn("Traceback", out)

    def test_plugin_manifest_that_is_not_json(self):
        (self.root / ".claude-plugin/plugin.json").write_text("{", encoding="utf-8")
        code, out = run_lint(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("cannot read the manifest", out)
        self.assertNotIn("Traceback", out)

    def test_plugin_manifest_needs_description(self):
        (self.root / ".claude-plugin/plugin.json").write_text(
            json.dumps({"name": "demo", "version": "1.0.0"}), encoding="utf-8")
        self.assert_fails("manifest needs 'description'")

    def test_marketplace_plugins_must_be_objects(self):
        (self.root / ".claude-plugin/marketplace.json").write_text(
            json.dumps({"name": "m", "plugins": ["demo"]}), encoding="utf-8")
        code, out = run_lint(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("'plugins' is not a list of objects", out)
        self.assertNotIn("Traceback", out)

    def test_marketplace_must_list_the_plugin(self):
        (self.root / ".claude-plugin/marketplace.json").write_text(
            json.dumps({"name": "m", "plugins": [{"name": "other", "source": "./"}]}), encoding="utf-8")
        self.assert_fails("no plugin entry is named 'demo'")

    def test_readme_must_list_each_skill(self):
        edit(self.root, "README.md", "**do-work** skill, ", "")
        self.assert_fails("skill 'do-work' is not in the skill table")

    def test_mustache_placeholder_with_spaces(self):
        edit(self.root, "commands/run.md", "$ARGUMENTS", "{{ RAW_PROMPT }}")
        self.assert_fails("is not a placeholder")

    def test_mustache_placeholder_in_skill_and_agent(self):
        edit(self.root, "skills/do-work/SKILL.md", "Read `", "Use {{INPUT}}. Read `")
        edit(self.root, "agents/helper.md", "You help.", "You help with {{TASK}}.")
        code, out = run_lint(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("skills/do-work/SKILL.md: {{INPUT}}", out)
        self.assertIn("agents/helper.md: {{TASK}}", out)

    def test_reference_file_can_name_a_banned_token(self):
        (self.root / "skills/do-work/reference/rules.md").write_text(
            "Claude Code does not replace `{{RAW_PROMPT}}`.\n", encoding="utf-8")
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)

    def test_plugin_root_reference_in_reference_file_must_exist(self):
        (self.root / "skills/do-work/reference/rules.md").write_text(
            "Run `${CLAUDE_PLUGIN_ROOT}/skills/do-work/scripts/gone.py`.\n", encoding="utf-8")
        self.assert_fails("skills/do-work/reference/rules.md: ${CLAUDE_PLUGIN_ROOT}/skills/do-work/scripts/gone.py does not exist")

    def test_skill_with_exactly_500_lines_passes(self):
        path = self.root / "skills/do-work/SKILL.md"
        text = path.read_text(encoding="utf-8")
        have = len(text.splitlines())
        path.write_text(text + "line\n" * (500 - have), encoding="utf-8")
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 500)
        code, out = run_lint(self.root)
        self.assertEqual(code, 0, out)

    def test_skill_with_501_lines_fails(self):
        path = self.root / "skills/do-work/SKILL.md"
        text = path.read_text(encoding="utf-8")
        have = len(text.splitlines())
        path.write_text(text + "line\n" * (501 - have), encoding="utf-8")
        self.assert_fails("501 lines")

    def test_skill_name_must_match_folder(self):
        edit(self.root, "skills/do-work/SKILL.md", "name: do-work", "name: work")
        self.assert_fails("does not match the folder name 'do-work'")

    def test_skill_description_too_long(self):
        edit(self.root, "skills/do-work/SKILL.md", "  Does the work.", "  " + "word " * 300)
        self.assert_fails("the limit is 1024")

    def test_skill_too_many_lines(self):
        path = self.root / "skills/do-work/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "line\n" * 500, encoding="utf-8")
        self.assert_fails("keep SKILL.md at 500 lines or fewer")

    def test_skill_folder_without_skill_md(self):
        (self.root / "skills/empty").mkdir()
        self.assert_fails("skill folder has no SKILL.md")

    def test_plugin_root_reference_must_exist(self):
        (self.root / "skills/do-work/reference/rules.md").unlink()
        self.assert_fails("${CLAUDE_PLUGIN_ROOT}/skills/do-work/reference/rules.md does not exist")

    def test_cross_reference_must_resolve(self):
        edit(self.root, "skills/do-work/SKILL.md", "`demo:helper`", "`demo:helpr`")
        self.assert_fails("demo:helpr names no agent, command, or skill")

    def test_readme_must_list_each_command(self):
        edit(self.root, "README.md", "`/demo:run` command", "a command")
        self.assert_fails("command /demo:run is not in the command table")

    def test_readme_must_list_each_agent(self):
        edit(self.root, "README.md", "**helper** agent, ", "")
        self.assert_fails("agent 'helper' is not in the agent table")

    def test_version_must_be_semver(self):
        make_plugin(self.root, version="1.0")
        self.assert_fails("version '1.0' is not MAJOR.MINOR.PATCH")

    def test_marketplace_version_must_match(self):
        market = self.root / ".claude-plugin/marketplace.json"
        data = json.loads(market.read_text(encoding="utf-8"))
        data["plugins"][0]["version"] = "0.9.0"
        market.write_text(json.dumps(data), encoding="utf-8")
        self.assert_fails("is not the plugin.json version '1.0.0'")


class VersionBumpTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_plugin(self.root)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")
        git(self.root, "checkout", "-q", "-b", "work")

    def tearDown(self):
        self._tmp.cleanup()

    def bump(self, version):
        edit(self.root, ".claude-plugin/plugin.json", '"version": "1.0.0"', f'"version": "{version}"')

    def test_no_change_passes(self):
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 0, out)

    def test_shipped_change_without_bump_fails(self):
        edit(self.root, "agents/helper.md", "You help.", "You help a lot.")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 1, out)
        self.assertIn("Increase the version", out)

    def test_shipped_change_with_bump_passes(self):
        edit(self.root, "agents/helper.md", "You help.", "You help a lot.")
        self.bump("1.0.1")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 0, out)

    def test_lower_version_fails(self):
        edit(self.root, "agents/helper.md", "You help.", "You help a lot.")
        self.bump("0.9.9")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 1, out)

    def test_committed_change_without_bump_fails(self):
        edit(self.root, "commands/run.md", "Parse from", "Read from")
        git(self.root, "commit", "-q", "-am", "change")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 1, out)

    def test_new_untracked_skill_without_bump_fails(self):
        path = self.root / "skills/more/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("---\nname: more\ndescription: More work. Use when asked.\n---\n\nBody.\n", encoding="utf-8")
        edit(self.root, "README.md", "**do-work** skill", "**do-work** and **more** skills")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 1, out)
        self.assertIn("Increase the version", out)

    def test_docs_and_skill_tests_do_not_need_a_bump(self):
        edit(self.root, "README.md", "# Demo", "# Demo plugin")
        path = self.root / "skills/do-work/tests/pass-clean.md"
        path.parent.mkdir(parents=True)
        path.write_text("A test draft.\n", encoding="utf-8")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 0, out)

    def test_rename_out_of_a_shipped_folder_without_bump_fails(self):
        (self.root / "archive").mkdir()
        git(self.root, "mv", "agents/helper.md", "archive/helper.md")
        edit(self.root, "README.md", "**helper** agent, ", "")
        edit(self.root, "skills/do-work/SKILL.md", " Then invoke `demo:helper`.", "")
        git(self.root, "commit", "-q", "-am", "archive the agent")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 1, out)
        self.assertIn("first: agents/helper.md", out)

    def test_new_file_with_non_ascii_name_without_bump_fails(self):
        path = self.root / "skills/do-work/reference/na\u00efve notes.md"
        path.write_text("Notes.\n", encoding="utf-8")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 1, out)
        self.assertIn("Increase the version", out)

    def test_version_must_pass_the_tip_of_the_base(self):
        edit(self.root, "agents/helper.md", "You help.", "You help a lot.")
        self.bump("1.0.1")
        git(self.root, "commit", "-q", "-am", "work bumps to 1.0.1")
        git(self.root, "checkout", "-q", "main")
        edit(self.root, "commands/run.md", "Parse from", "Read from")
        self.bump("1.0.1")
        git(self.root, "commit", "-q", "-am", "main also bumps to 1.0.1")
        git(self.root, "checkout", "-q", "work")
        code, out = run_lint(self.root, "--base", "main")
        self.assertEqual(code, 1, out)
        self.assertIn("main has 1.0.1", out)

    def test_unknown_base_fails(self):
        code, out = run_lint(self.root, "--base", "no-such-ref")
        self.assertEqual(code, 1, out)
        self.assertIn("cannot find a merge base", out)


if __name__ == "__main__":
    unittest.main()
