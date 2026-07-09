import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { formatToolResultSections, ToolCallBlock } from "./tool-call-block";

test("formatToolResultSections turns JSON result dumps into labeled sections", () => {
  const sections = formatToolResultSections(
    JSON.stringify({
      success: true,
      name: "obsidian",
      description: "Read, search, and create notes.",
      content: "---\nname: obsidian\n---\n\n# Obsidian Vault",
      path: "note-taking/obsidian/SKILL.md",
      setup_needed: false,
    })
  );

  assert.deepEqual(
    sections.map((section) => [section.label, section.value]),
    [
      ["Status", "success"],
      ["Name", "obsidian"],
      ["Description", "Read, search, and create notes."],
      ["Path", "note-taking/obsidian/SKILL.md"],
      ["Setup Needed", "false"],
      ["Content", "---\nname: obsidian\n---\n\n# Obsidian Vault"],
    ]
  );
});

test("ToolCallBlock renders parsed JSON result labels", () => {
  const markup = renderToStaticMarkup(
    <ToolCallBlock
      block={{
        type: "tool_call",
        toolName: "skill_view",
        input: {},
        result: JSON.stringify({
          success: true,
          name: "obsidian",
          content: "# Obsidian Vault",
        }),
      }}
    />
  );

  assert.match(markup, /Status/);
  assert.match(markup, /success/);
  assert.match(markup, /Content/);
  assert.match(markup, /Obsidian Vault/);
});
