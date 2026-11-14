---
description: A request to start a project in an Obsidian vault. The obsidian-project skill must fire.
expected_outcome: Claude invokes the obsidian-project skill. The run has no Bash or Write grant, so it cannot create the notes.
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Start a new project in my Obsidian vault called Photo Renamer. It is a Rust CLI that renames photos by their EXIF date.
