## Skills

A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.

### Available skills

- skill-creator: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Codex's capabilities with specialized knowledge, workflows, or tool integrations. (file: /Users/tony/.codex/skills/.system/skill-creator/SKILL.md)
- skill-installer: Install Codex skills into `$CODEX_HOME/skills` from a curated list or a GitHub repo path. Use when a user asks to list installable skills, install a curated skill, or install a skill from another repo, including private repos. (file: /Users/tony/.codex/skills/.system/skill-installer/SKILL.md)

### How to use skills

- Discovery: The list above is the skills available in this session. Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill with `$SkillName` or plain text, or the task clearly matches a skill's description, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing or blocked: If a named skill is not in the list or the path cannot be read, say so briefly and continue with the best fallback.
- How to use a skill:
  1. After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2. When `SKILL.md` references relative paths, resolve them relative to the skill directory listed above first, and only consider other paths if needed.
  3. If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request. Do not bulk-load everything.
  4. If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  5. If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Coordination and sequencing:
  1. If multiple skills apply, choose the minimal set that covers the request and state the order you will use them.
  2. Announce which skill or skills you are using and why in one short line. If you skip an obvious skill, say why.
- Context hygiene:
  1. Keep context small: summarize long sections instead of pasting them and only load extra files when needed.
  2. Avoid deep reference chasing: prefer opening only files directly linked from `SKILL.md` unless you are blocked.
  3. When variants exist, pick only the relevant reference file or files and note that choice.
- Safety and fallback: If a skill cannot be applied cleanly due to missing files or unclear instructions, state the issue, pick the next-best approach, and continue.
