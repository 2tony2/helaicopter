# OATS Design For Parallel Data Modeling Architecture Review

## Executive Summary

Helaicopter already has a Markdown-first OATS setup, a repo-level `.oats/config.toml`, and an emerging pattern for orchestrating multi-task work across branches and worktrees. The new need is different from implementation orchestration: run a portfolio of data-modeling and architecture-analysis prompts from `/Users/tony/Code/agent-harness/data_modeling_design_agents_repo` as parallel Claude Opus tasks, have them inspect one or more real codebases and data surfaces through different lenses, and then produce a final synthesized recommendation package.

The target state is a reusable OATS analysis run that:
- uses one shared architecture brief as the common input
- dispatches a pinned catalog of agent prompts from `agents/` unconditionally and in parallel
- runs all tasks with Claude Opus
- writes one output file per lens into deterministic paths on a shared feature worktree
- finishes with a final Claude Opus synthesis task that compiles the lens outputs into targeted recommendations, explicit trade-offs, and questions for deeper staff-level exploration

This is intentionally an analysis workflow, not a code implementation workflow. The main artifact is a branch containing design suggestions and synthesis documents rather than code changes across the target systems.

## Goals

- Create a reusable OATS configuration and run definition for architecture and data-modeling analysis.
- Run a pinned set of agent prompts from the external data-modeling agent repository in parallel, regardless of their original conditional routing rules.
- Give every parallel task the same shared brief so outputs are comparable across lenses.
- Keep task outputs isolated by file path while allowing a shared feature worktree and branch.
- Produce a final Opus synthesis document that identifies likely-fit approaches for the studied codebases, databases, and APIs.
- Make assumptions, tensions, and unresolved questions explicit so a staff-engineer follow-up pass can deepen the investigation.

## Non-Goals

- Implementing the recommended architecture or data model in the studied codebases.
- Preserving the target repository's conditional orchestration logic for this run type.
- Supporting arbitrary non-Markdown input formats in the first version.
- Letting parallel tasks collaboratively edit a shared synthesis file.
- Treating the resulting branch as a production-ready implementation branch.

## Current State

### OATS in Helaicopter

- Repo-level OATS configuration already exists in `.oats/config.toml`.
- OATS uses Markdown-first run definitions and already models parallel task graphs with dependencies.
- The repository already contains design and plan documents for more implementation-oriented OATS runs.
- Existing git/worktree settings assume branch-oriented OATS execution, with task branches and integration branches available when needed.

### External data-modeling prompt repository

- `/Users/tony/Code/agent-harness/data_modeling_design_agents_repo` contains:
  - an orchestration map in `AGENTS.md`
  - thirteen agent prompt files under `agents/`
  - templates, playbooks, checklists, and research material
- The external repository is written for design-package generation and agent-style delegation, but this new OATS workflow will treat those agent prompts as a fixed parallel prompt set.

## Settled Design Decisions

### 1. Unconditional parallel dispatch of a pinned agent catalog

The run should execute a pinned catalog of agent prompt files from the external repository for every analysis session. This design explicitly does not preserve the target repository's original "always run" and "conditional specialist" routing logic. The value here is breadth of perspective, not strict prompt-economy.

The first version should pin the current thirteen prompt files by path and name. The run must not dynamically discover new files in the external repository at execution time. Updating the lens catalog is a deliberate repo change, not an ambient side effect of the external repository evolving.

### 2. Shared brief, not embedded one-off prompts

Each task reads the same architecture brief stored in this repository. The brief captures:
- codebases under study
- relevant databases, APIs, and system boundaries
- the architectural question being investigated
- the required output contract

The run definition should reference the brief rather than duplicating large context blocks into every task description.

### 3. Shared worktree and feature branch

All tasks write into the same feature worktree and feature branch. This is acceptable because the tasks are analysis-oriented and will write only to unique markdown files under deterministic locations. No task should edit another task's output file.

### 4. One output file per lens

Each parallel task owns exactly one markdown output path. That path is stable and derivable from the agent file name. This avoids merge conflicts and keeps review straightforward.

### 5. Final synthesis is a separate dependent task

The final Opus synthesis task runs only after all lens-specific analysis files exist. Its job is not to restate every agent output; it must reconcile them, identify patterns that appear defensible for the actual systems under study, and produce targeted next-step questions.

## Proposed File Layout

The first implementation of this design should introduce the following files:

- `docs/oats/data-modeling-architecture-brief.md`
- `docs/oats/data-modeling-output-conventions.md`
- `docs/oats/data-modeling-agent-catalog.md`
- `examples/data_modeling_design_agents_oats_run.md`

The run should snapshot the shared brief into the run-output directory before any parallel dispatch. Run outputs should then land under a deterministic directory such as:

- `docs/oats/runs/data-modeling-design/<run-slug>/brief.md`
- `docs/oats/runs/data-modeling-design/<run-slug>/agents/<agent-output>.md`
- `docs/oats/runs/data-modeling-design/<run-slug>/opus-synthesis.md`

The run slug should be stable enough to distinguish sessions without requiring the tasks to invent filenames on the fly.

### Deterministic naming rules

- `<run-slug>` should be generated from a UTC timestamp plus a short topic slug, for example `20260319T154500Z-architecture-review`
- `<agent-output>` should be the source prompt filename without the `.md` suffix
- the synthesis output path is always exactly `opus-synthesis.md`

Tasks must not generate ad hoc filenames.

## Reproducibility And Prompt Source Contract

The design depends on prompt files that live outside this repository, so reproducibility needs to be explicit.

### Agent catalog

`docs/oats/data-modeling-agent-catalog.md` should pin:
- the external repository root path expected on the local machine
- the exact prompt files used by the run
- the file-ordering contract
- the exact external repository commit SHA expected by the run
- optionally the expected SHA256 for each pinned prompt file if file-level validation is easier than repo-level validation in the implementation

### Missing or changed prompt sources

If a pinned prompt file is missing, renamed, or changed relative to the pinned commit SHA or file hash validation rule, the run should fail before dispatch rather than silently substituting a different prompt set. The failure should tell the operator to refresh the catalog intentionally.

### Portability

This design is reusable within the user's environment, not fully machine-agnostic in its first version. The implementation should make that boundary explicit. A later version may vendor prompt content locally or support a configurable external-repo path, but the first version should prefer a pinned local-path contract over implicit portability promises.

## Shared Brief Design

The shared brief is the most important control surface in this workflow. It should contain enough structure to make the parallel outputs comparable while still letting each lens do genuine reasoning.

`docs/oats/data-modeling-architecture-brief.md` is the editable source brief. For execution, the run must copy or render that source brief into `docs/oats/runs/data-modeling-design/<run-slug>/brief.md` and all tasks must read the immutable run-scoped snapshot instead of the mutable source file.

### Required brief sections

- scope and purpose of the review
- repositories or paths under analysis
- known databases, schemas, APIs, queues, and integration boundaries
- suspected architectural pain points or unknowns
- expected audience for the output
- what "good" recommendations should help decide
- explicit instructions to inspect real code and configuration rather than speculate when evidence is available

### Required analysis rubric

Every agent should be asked to comment on the following when relevant:
- current system boundaries
- likely domains and aggregates
- database responsibilities and overlap
- API ownership and coupling
- integration-model candidates
- consumption/publication-model candidates
- historical, audit, and replay requirements
- semantic and metric consistency risks
- platform and operability considerations
- governance or ownership concerns

The brief should also tell the agents to mark evidence, assumptions, and unresolved gaps explicitly.

## Analysis Input Access Contract

The design must define how analysis targets are presented to the run so tasks can inspect real systems without inventing access paths.

### Required target manifest in the shared brief

The shared brief should include a small manifest for every analyzed surface:
- local repository path or paths
- relevant subdirectories to inspect first
- known database or schema artifacts available locally
- API specs, router paths, client modules, or contract files available locally
- whether live credentials or remote systems are in scope

### Missing access behavior

If a task cannot access a repository, schema artifact, API contract, or credentialed environment named in the brief, it must:
- record the missing access explicitly under `assumptions` or `open questions`
- downgrade its claim strength accordingly
- avoid pretending it verified a system it could not inspect

The run should not fail merely because a live database is unavailable, but it must fail if the shared brief omits the local paths needed to inspect the intended codebases.

## Task Model

### Parallel lens tasks

There should be one task for each prompt listed in the pinned agent catalog. In the first version, that pinned set is:

- `00_lead_data_modeling_architect.md`
- `01_requirements_and_business_process_analyst.md`
- `02_source_profiling_and_reality_check.md`
- `03_pattern_selection_and_tradeoff_architect.md`
- `04_dimensional_modeling_specialist.md`
- `05_inmon_enterprise_data_warehouse_specialist.md`
- `06_data_vault_2_0_specialist.md`
- `07_streaming_and_event_modeling_specialist.md`
- `08_lakehouse_and_platform_physical_design_specialist.md`
- `09_semantic_layer_and_metrics_specialist.md`
- `10_governance_quality_and_lineage_specialist.md`
- `11_repository_maintainer_and_design_reviewer.md`
- `12_anchor_modeling_specialist.md`

Each task should:
- use Claude Opus
- read the shared brief
- read its assigned external agent prompt file
- inspect the specified codebases and data surfaces
- write a single markdown file to its owned output path
- avoid editing shared files outside that output path

### Final synthesis task

The final task should depend on all thirteen agent outputs. It should also use Claude Opus.

Its input set should include:
- the shared brief
- all lens output files
- optionally the external orchestration map in `AGENTS.md` for context

Its output should be `opus-synthesis.md` and must include:
- executive recommendation
- architecture/modeling options that look most defensible
- conflicts or tensions between lenses
- assumptions that need validation in the actual systems
- targeted recommendations
- questions for further exploration by a senior or staff engineer

## Output Contract

### Lens-specific outputs

Each per-agent output file should use a common section shape so they can be synthesized reliably:

- purpose of this lens
- evidence observed
- assumptions
- findings
- recommendations
- risks and trade-offs
- open questions

Not every section needs the same length, but the headings should stay stable.

### Final synthesis output

The synthesis file should be more selective. It should not become a thirteen-document dump. The preferred structure is:

- executive summary
- recommended architecture direction
- recommended data-modeling direction
- areas where multiple lenses agree
- disagreements and why they matter
- immediate follow-up investigations
- staff-engineer question set

## Branch And Worktree Strategy

This workflow uses one shared feature worktree and one feature branch because the outputs are documentation artifacts with non-overlapping paths.

### Constraints

- each task owns one file path and writes nowhere else
- the synthesis task owns only the final synthesis file
- shared inputs are treated as read-only during execution
- no task performs git branching, worktree creation, rebases, pulls, or cleanup during the analysis run
- the run creates output directories up front before parallel task dispatch
- the branch is a review artifact branch, not a final implementation branch

### Naming

Branch naming should make the review purpose explicit. The exact prefix may follow OATS defaults or a manual branch policy, but it should identify the run as a data-modeling analysis branch rather than implementation work.

## Provider And Model Choice

Claude Opus is the required model family for both the lens tasks and the final synthesis task. The run definition should therefore make the provider selection explicit instead of relying on defaults from the repo-level OATS config.

This design assumes OATS can express agent/provider selection per task or per run. If the current runtime only supports repo-default agent choices, then this workflow is blocked until that override exists.

The run must fail fast if it cannot guarantee Claude Opus selection for the lens tasks and the synthesis task. Silent fallback to Codex or an unspecified model is explicitly disallowed for this workflow.

## Failure Model

The primary risks in this workflow are not runtime crashes but analysis drift and output inconsistency.

### Main failure cases

- tasks produce incomparable output formats
- tasks speculate instead of inspecting real systems
- tasks overwrite shared files
- tasks compete on git or worktree operations in the shared checkout
- synthesis collapses nuance into generic advice
- shared brief is too vague and causes prompt divergence

### Mitigations

- use a shared brief with an explicit rubric
- require a target manifest with local inspection paths
- pin the external prompt catalog and reviewed version marker
- define deterministic output file paths
- define stable required headings for lens outputs
- prohibit per-task git/worktree mutations during the run
- make synthesis depend on all lens outputs
- keep the synthesis task focused on reconciliation, recommendation, and questions rather than repetition

## Implementation Notes

The implementation should favor the smallest possible change set that works with the existing OATS runtime:

- reuse Markdown-first run definitions
- reuse current repo-level OATS config where possible
- add run-local instructions only where Claude/Opus selection or output-path rules need to differ
- avoid building new orchestration semantics when a run-spec convention is sufficient

If the current OATS runtime cannot target Claude Opus for these tasks, that gap should be made explicit in the implementation plan rather than hidden inside the design.

## Testing And Validation Strategy

This workflow is documentation-oriented, but it still needs verification:

- validate the run definition parses correctly
- validate task dependency structure so the synthesis task waits for all lens tasks
- validate every task description points to a unique output file
- validate the run creates shared output directories before parallel dispatch
- validate no task instructions ask for git/worktree mutation beyond writing owned files
- validate the chosen provider for the run is Claude Opus rather than the repo default
- perform one smoke run against a narrow test brief before using the workflow on a broad architecture study

The smoke run should be reviewed against qualitative acceptance criteria:
- each lens output includes the required headings
- each lens output cites concrete code, config, schema, or contract evidence when locally available
- missing access is surfaced explicitly rather than hidden
- the synthesis document identifies agreements, disagreements, and next-step questions without collapsing into generic pattern summaries

## Open Questions

- whether the current OATS runtime already supports per-task or per-run Claude/Opus overrides cleanly
- whether the shared brief should point at a fixed set of codebase paths or support a small parameter block per run
- whether the final synthesis should also emit a condensed summary for a dashboard or PR body
- whether the repository should preserve historical run outputs in-tree or treat them as disposable branch artifacts

## Recommendation

The best first version is a Markdown-first OATS analysis workflow that treats the external data-modeling prompt repository as a fixed parallel lens catalog. Use one shared architecture brief, one shared feature worktree, one owned output file per lens, and one final Opus synthesis task. Keep the implementation minimal and deterministic so the value comes from the quality of the comparative analysis rather than from new orchestration complexity.
