# Run: YAWT Workspace Shell And Conflict Review

## Tasks

### runtime_state
Title: T003 Runtime State

Implement local runtime persistence for attribution spans, operation logs, preview cache, session state, and conflicts.

Acceptance criteria:
- runtime DB initializes automatically
- migration path is versioned
- saves create operation log entries
- conflicts can be created, queried, and resolved

Notes:
- do not store primary authored content in SQLite

### server_shell
Title: T009 Server APIs And Workspace Shell
Depends on: runtime_state

Build the main FastAPI surface and the base workspace UI shell.

Acceptance criteria:
- author can navigate book/chapter/section/block/research objects
- right panel tabs exist and are wired
- core APIs return stable data

Notes:
- include routers for chapters, blocks, research, threads, conflicts, preview, and settings
- include workspace layout, binder tree, and right panel tabs
- do not implement final patch review or live mode

### conflict_review
Title: T011 Patch Review And Conflict UX
Depends on: server_shell

Build Git-style patch review and conflict resolution UX.

Acceptance criteria:
- participant changes can be reviewed before and after apply
- conflicts are understandable and resolvable
- file-by-file Obsidian conflicts are surfaced clearly

Notes:
- include patch panel, accept/reject/revise flows, conflict panel, object-aware diffs, and manual merge tools
- include server endpoints for review actions
