# Layered Repo Boundaries Design

## Executive Summary

This design reshapes Helaicopter around stricter global layers rather than feature-colocated modules. The goal is to make frontend and backend complexity grow inside well-defined boundaries instead of expanding through catch-all folders and cross-layer imports.

The frontend keeps Next.js routing separate from page composition, feature behavior, domain concepts, and shared infrastructure. The backend keeps HTTP transport, application workflows, domain rules, ports, adapters, and contracts separate. Both sides use the same high-level principle: code should live in the narrowest layer that can own it without reaching across boundaries.

## Goals

- Preserve a global layered architecture instead of moving to full feature colocation.
- Make it easier to grow deeper complexity without turning `src/components`, `src/lib`, or backend schema/application folders into mixed-responsibility buckets.
- Sharpen dependency direction so each layer has a predictable set of allowed imports.
- Make route files and HTTP entrypoints thin so complexity accumulates in the correct layer.
- Provide a migration path that can be executed incrementally without a big-bang rewrite.

## Non-Goals

- Rewriting the product around a new feature taxonomy in one pass.
- Adopting a fully ceremonial clean-architecture layout that adds indirection without clear value.
- Renaming folders without changing ownership and import rules.
- Moving frontend and backend into a shared cross-language domain model.
- Solving every legacy placement problem as part of the first migration slice.

## Current State

### Frontend

The frontend already distinguishes route files under `src/app/` from reusable UI under `src/components/`, hooks under `src/hooks/`, and general utilities under `src/lib/`. That is a useful start, but the top-level buckets are still broad enough that multiple concerns can accumulate in the same folder:

- route-adjacent page composition can remain inside `src/app/`
- product behavior and domain-specific UI are mixed together in `src/components/*`
- `src/lib/` can become a generic destination for unrelated concerns
- `src/hooks/` separates code by React mechanism rather than by ownership

This works at moderate scale, but it becomes harder to predict where deeper logic belongs once features gain more state, data boundaries, and UI variants.

### Backend

The backend already has a layered shape under `python/helaicopter_api/` with `router/`, `application/`, `ports/`, `adapters/`, `schema/`, `bootstrap/`, `server/`, and `pure/`. The pressure point is not the existence of layers; it is that some folders still act as broad buckets:

- transport contracts and domain-oriented shapes can blur together in `schema/`
- orchestration logic can leak between `router/`, `application/`, and adapter code
- `pure/` is not an obvious architectural boundary from the name alone

The backend therefore has the right instinct but needs clearer ownership and more explicit inward versus outward dependencies.

## Design Decisions

### 1. Keep global layers, but subdivide them by stable domains

The repo should continue to separate layers globally rather than colocating everything by feature. Within each layer, folders should be subdivided by product area or stable concept names such as `conversations`, `analytics`, `plans`, `databases`, or `orchestration`.

This provides two forms of navigation:

- horizontal navigation by architectural role
- vertical navigation by domain name inside that layer

That combination makes deeper complexity easier to manage than the current broad buckets.

### 2. Make entrypoints thin

Frontend route files and backend HTTP handlers should become thin entrypoints:

- `src/app/` should primarily define routing, layouts, params, and screen entry
- `python/helaicopter_api/router/` should primarily parse requests, invoke application services, and shape responses

This prevents orchestration logic from diffusing into framework-owned folders.

### 3. Split composition from behavior on the frontend

Page-level assembly should live separately from reusable product behavior:

- `views/` composes screens from lower-level pieces
- `features/` owns interactive capabilities and user-facing behavior
- `entities/` owns durable product concepts and concept-level presentation helpers
- `shared/` owns cross-cutting UI primitives, hooks, client plumbing, utilities, and base types

This avoids the current tension where page composition and reusable behavior both drift into `components/`.

### 4. Split contracts from domain on the backend

Transport schemas should not carry business meaning by default. The backend should distinguish:

- `contracts/` for request, response, and integration DTOs
- `domain/` for business concepts and rules
- `application/` for use-case coordination

This makes it easier to change HTTP or adapter-facing contracts without implying a domain model change.

### 5. Keep external dependencies behind ports and adapters

Filesystem access, SQLite access, legacy orchestration integration, and artifact reads stay in `adapters/` behind interfaces defined by `ports/`. Neither domain nor request-layer code should know external layout details directly.

## Target Structure

### Frontend target structure

```text
src/
  app/           # Next.js routes and route-only files
  views/         # page-level composition
  features/      # user-facing capabilities by product area
  entities/      # durable product concepts and concept-level UI/model helpers
  shared/        # cross-cutting ui, hooks, client, utils, types
```

An expected steady-state shape is:

```text
src/
  app/
    conversations/
    plans/
    orchestration/
    pricing/
    docs/
  views/
    conversations/
    plans/
    orchestration/
    analytics/
  features/
    analytics/
    conversations/
    databases/
    evaluations/
    orchestration/
    plans/
    prompts/
  entities/
    conversation/
    plan/
    database/
    orchestration/
  shared/
    ui/
    hooks/
    client/
    utils/
    types/
```

### Backend target structure

```text
python/helaicopter_api/
  router/        # HTTP layer only
  application/   # use cases and workflow orchestration
  domain/        # business concepts and rules
  ports/         # interfaces owned by the inner layers
  adapters/      # filesystem/sqlite/legacy-orchestration/artifact implementations
  contracts/     # request/response schemas and DTOs
  bootstrap/     # wiring and dependency assembly
  server/        # FastAPI app entrypoints and config
```

An expected steady-state shape is:

```text
python/helaicopter_api/
  router/
    conversations/
    analytics/
    orchestration/
    databases/
  application/
    conversations/
    analytics/
    orchestration/
    databases/
  domain/
    conversations/
    analytics/
    orchestration/
    databases/
  ports/
  adapters/
    claude_fs/
    codex_sqlite/
    app_sqlite/
    oats_artifacts/
  contracts/
  bootstrap/
  server/
```

The existing `schema/` folder should be retired in favor of `contracts/`, and `pure/` should either be absorbed into `domain/` or renamed only if a narrower ownership boundary is discovered during migration.

## Dependency Rules

### Frontend

- `app` may import `views`, `features`, `entities`, and `shared`
- `views` may import `features`, `entities`, and `shared`
- `features` may import `entities` and `shared`
- `entities` may import `shared`
- `shared` must not depend on repo-specific higher layers

Additional frontend rules:

- route files should not accumulate business logic, data shaping, or large UI trees
- generic hooks should live in `shared/hooks`; feature-specific hooks should live inside the owning `features/*` folder
- generic client plumbing should live in `shared/client`; feature-specific fetch helpers may live in the owning feature when they are not broadly reusable
- `shared/ui` is for reusable primitives, not domain-branded widgets

### Backend

- `router` may import `application`, `contracts`, and `bootstrap`
- `application` may import `domain`, `ports`, and `contracts`
- `domain` should depend only on itself and very small shared primitives
- `ports` are defined inward and implemented outward
- `adapters` may import `ports`, `domain`, and `contracts`
- `contracts` should not hold business logic
- `server` and `bootstrap` wire the runtime but should not absorb use-case behavior

Additional backend rules:

- router code should stop at HTTP concerns
- application code should coordinate workflows and cross-port behavior
- domain code should express business meaning without knowing HTTP, SQL, filesystem layout, or framework details
- adapter-specific translation should stay in adapters rather than leaking into application services

## Migration Strategy

The migration should be incremental and slice-based rather than a one-time repo move.

### Phase 1: Introduce target folders and move shared frontend primitives

- create `src/shared/`
- move generic UI primitives from `src/components/ui` into `src/shared/ui`
- move generic hooks from `src/hooks` into `src/shared/hooks`
- move generic client and utility code out of `src/lib` into `src/shared/client`, `src/shared/utils`, and `src/shared/types`

The goal of this phase is to shrink the broadest generic buckets first.

### Phase 2: Make route files thin

- create `src/views/`
- move page-composition code out of `src/app/*` into `src/views/*`
- leave route files in `src/app/*` as narrow entrypoints that bind params and render a view

This creates a stable screen-composition layer before feature extraction begins.

### Phase 3: Extract frontend product modules

- create `src/features/*` folders for the major product areas already visible in the repo
- move interactive domain-specific code out of `src/components/*` into those owning feature folders
- create `src/entities/*` only where a durable concept has cross-feature reuse or concept-level mapping logic

This phase should be domain-by-domain, not all at once.

### Phase 4: Split backend contracts from domain

- create `python/helaicopter_api/contracts/`
- migrate request/response and integration DTOs out of `schema/`
- evaluate `pure/` contents and move them into `domain/` where they express business meaning

This phase makes backend semantics more legible before deeper service refactors.

### Phase 5: Tighten application ownership

- reorganize `application/` by domain area
- ensure multi-step workflows and cross-port coordination live there
- remove orchestration leakage from router and adapters

### Phase 6: Normalize adapter boundaries

- keep filesystem, sqlite, artifact, and orchestration integrations entirely inside `adapters/`
- ensure ports describe the required behavior from the perspective of the inner layers

## Guardrails

The structure will only stay healthy if the repo also enforces placement and import rules.

Recommended guardrails:

- add frontend lint rules that restrict imports across layers
- document allowed import directions in a short architecture note
- require route files to stay thin during review
- avoid adding new generic catch-all folders
- prefer moving misplaced code into an existing architectural home instead of creating exceptions
- treat `lib` as a migration source, not a permanent destination
- treat transport schemas as contracts, not as the default home for business meaning

## Risks And Mitigations

### Risk: the migration becomes a cosmetic rename pass

Mitigation: pair folder moves with ownership and dependency rules. Do not count a move as complete if code keeps crossing the same boundaries.

### Risk: too much indirection on the frontend

Mitigation: introduce `entities/` only where it buys real clarity or reuse. Not every concept needs its own entity module immediately.

### Risk: backend `domain/` becomes either anemic or overloaded

Mitigation: use `application/` for orchestration and `contracts/` for transport concerns so `domain/` can stay narrow and meaningful.

### Risk: long migration tail from compatibility imports

Mitigation: move one product area at a time and remove compatibility imports as part of each slice instead of leaving permanent aliases.

## Success Criteria

- A new contributor can predict where to add route logic, page composition, feature behavior, domain concepts, and shared utilities without reading unrelated files.
- Frontend route files are visibly thinner and stop serving as composition-heavy screens.
- `src/components`, `src/hooks`, and `src/lib` are either retired or dramatically narrowed in scope.
- Backend transport contracts are clearly separate from business/domain logic.
- Backend application workflows are easier to identify because they no longer leak through router and adapter layers.
- Import direction can be checked in review and partially enforced by tooling.

## Deferred Follow-Up

- Decide whether repo-level path aliases should mirror the new layers after the folder migration begins.
- Evaluate whether backend domains should eventually split into separate packages only if the internal module boundaries become too large.
- Add architecture tests or lint checks after the target layout has stabilized enough to encode the rules.
