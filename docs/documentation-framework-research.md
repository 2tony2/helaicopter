# Documentation Framework Research

## Scope and repo fit

This repo is already split between a Next.js 16 frontend and a FastAPI backend. It also already exposes a first-class OpenAPI surface (`/openapi.json`) and keeps narrative docs in repo-local Markdown under `docs/`.

That makes the decision less about "which docs tool is best in the abstract" and more about which option best fits:

- mixed product + developer docs
- generated API reference from FastAPI/OpenAPI
- repo-local authoring and review
- self-hosting or simple deploy paths
- low migration overhead from the current `docs/` Markdown notes

## Options evaluated

### 1. Sphinx

**What it is**

Sphinx is the mature Python-centric documentation system. For this repo, the realistic setup would be:

- `Sphinx`
- `MyST-Parser` so authors can keep writing Markdown instead of pure reStructuredText
- `sphinx.ext.autodoc` or `sphinx-autoapi` for Python package reference
- `sphinxcontrib-openapi` or `sphinxcontrib-redoc` for HTTP API reference from FastAPI's OpenAPI spec

**Pros**

- Best Python ecosystem fit for `python/helaicopter_api/` and `helaicopter_db`
- Strong API reference story for Python modules, especially if code docstrings become a real maintenance target
- Excellent static output and boring, stable CI story
- Good cross-references, versioning, PDF/epub output, and long-form technical writing support

**Cons**

- Feels separate from the existing product frontend and design system
- API docs for FastAPI/OpenAPI are not first-class in core Sphinx; they depend on extra extensions
- More moving parts if the goal is one cohesive docs experience across product docs, guides, and API reference
- Authoring ergonomics are only "good" if MyST is added; raw rST would be a step backward for this repo

**Migration cost**

- `Medium`
- Low for moving existing `docs/*.md` into MyST-backed Sphinx pages
- Medium/high if we also want polished frontend-like navigation and OpenAPI rendering

**Authoring ergonomics**

- `Good with MyST`, `mixed without it`
- Best for engineers comfortable with Python tooling and structured docs builds

**API docs fit**

- `Good for Python package docs`
- `Fair to good for OpenAPI`, but only via add-ons rather than a first-party workflow

**Hosting fit**

- `Very good` for static hosting: GitHub Pages, Netlify, Vercel static output, S3, Read the Docs
- Weak fit if the goal is "keep docs inside the main Next.js app shell"

### 2. Next.js-native docs path

This bucket has two sub-paths:

- bare `@next/mdx` inside the existing app
- a docs-focused layer on top of Next.js, with `Fumadocs` the best fit here

#### 2a. Raw Next.js MDX

**Pros**

- Lowest conceptual overhead
- Keeps docs inside the existing app and deploy flow
- Easy to reuse current UI components, auth rules, and layout patterns

**Cons**

- You build most docs UX yourself: sidebar generation, page metadata, search, structured navigation, code presentation, API reference pages
- Easy to underinvest and end up with "just a folder of MDX pages"
- OpenAPI integration becomes custom work

**Migration cost**

- `Low` for basic docs pages
- `Medium` once search, navigation, and API reference are required

**Authoring ergonomics**

- `Good`
- MDX is already aligned with the frontend stack, but content structure conventions must be invented locally

**API docs fit**

- `Fair`
- Works, but mostly via custom code or third-party packages

**Hosting fit**

- `Excellent` if docs should live inside the existing Next.js deploy target

#### 2b. Fumadocs on top of Next.js

**Why it stands out**

Fumadocs keeps the "docs live inside our Next.js app" model, but adds the missing docs primitives. Its official OpenAPI integration is materially stronger than raw MDX and more aligned with this repo's existing stack than Sphinx or Mintlify.

**Pros**

- Native fit for the current stack: Next.js, React, Tailwind, component reuse
- Official OpenAPI integration can render API pages from local files or external URLs
- Easier to keep product docs, operational docs, and API reference in one site
- Strong authoring ergonomics with MDX and structured content collections
- Self-hosted and repo-local; no SaaS lock-in

**Cons**

- Still a JavaScript/docs-framework choice, so Python autodoc is weaker than Sphinx
- More initial setup than raw MDX
- Some docs architecture decisions still need to be made locally: route structure, content source, search, versioning

**Migration cost**

- `Low to medium`
- Existing Markdown docs can mostly move with limited rework
- OpenAPI integration is easier than in Sphinx or raw MDX

**Authoring ergonomics**

- `Very good`
- Best fit for a repo already centered on Next.js and Markdown-like docs

**API docs fit**

- `Very good for OpenAPI`
- `Fair` for Python module reference unless we separately generate those docs or decide they are not a priority

**Hosting fit**

- `Excellent`
- Same hosting model as the app: Vercel, self-hosted Next.js, or a dedicated docs deploy from the same codebase

#### 2c. Nextra as another Next.js-native option

Nextra is also credible here, but it looks more like a docs-themed site framework than a flexible "fit this into the current app" toolkit. It is a viable secondary choice if the goal becomes a more standard external docs site. It is less compelling than Fumadocs here because OpenAPI support is not as central and the repo already has Tailwind/shadcn-style UI patterns that Fumadocs matches well.

### 3. OpenClaw's approach: Mintlify

**What OpenClaw is using**

The current OpenClaw docs site is powered by `Mintlify`. Their public docs footer explicitly says the documentation is built and hosted on Mintlify.

**Pros**

- Fastest route to a polished external docs portal
- Strong default IA, navigation, search, and public-facing docs presentation
- Good OpenAPI story: Mintlify can generate API reference sections directly from an OpenAPI file and provides an interactive API playground
- Good choice for public product docs where design polish and time-to-launch matter more than deep repo integration

**Cons**

- More SaaS/platform coupling than the other options
- Less control over the runtime and layout than a repo-native Next.js docs site
- Harder to make docs feel like a seamless part of the main Helaicopter app
- Repo-local authoring is still possible, but the workflow centers around Mintlify config conventions rather than the current app stack

**Migration cost**

- `Medium`
- Content migration is straightforward, but hosting, config, and workflow shift to a dedicated docs platform

**Authoring ergonomics**

- `Very good` for product-style docs writers
- Better than Sphinx for general docs writing, but less flexible than owning the full Next.js app

**API docs fit**

- `Very good for OpenAPI`
- `Weak` for Python package reference compared with Sphinx

**Hosting fit**

- `Very good` if an external hosted docs property is acceptable
- `Poorer` if docs must stay fully inside the current app/runtime and repo-owned deploy model

## Comparison summary

| Option | Pros | Cons | Migration cost | Authoring ergonomics | API docs fit | Hosting fit |
| --- | --- | --- | --- | --- | --- | --- |
| Sphinx + MyST + AutoAPI/OpenAPI extensions | Best Python ecosystem fit; strong long-form and module docs; mature static builds | Separate from current frontend stack; OpenAPI depends on extensions; more tooling split | Medium | Good with MyST | Good for Python, fair/good for OpenAPI | Very good for static hosting |
| Next.js + raw MDX | Lowest setup; native to current app | You build docs UX yourself; OpenAPI mostly custom | Low to medium | Good | Fair | Excellent |
| Next.js + Fumadocs | Best stack alignment; strong OpenAPI integration; self-hosted; one cohesive docs site | Slightly more setup than raw MDX; weaker than Sphinx for Python autodoc | Low to medium | Very good | Very good for OpenAPI, fair for Python module docs | Excellent |
| Mintlify (OpenClaw's model) | Fastest polished public docs; strong OpenAPI/reference UX | SaaS coupling; less runtime control; less integrated with app | Medium | Very good | Very good for OpenAPI, weak for Python module docs | Very good if external hosted docs are acceptable |

## Recommendation

### Recommended default: Next.js-native docs, specifically Fumadocs

This is the best default for Helaicopter.

Why:

- the repo already pays the Next.js/React/Tailwind cost
- existing docs are Markdown-first, not docstring-first
- the most important API-doc problem here is FastAPI/OpenAPI, not Python module autodoc
- keeping docs in the same app and repo reduces operational surface area
- Fumadocs gives us docs-grade navigation and OpenAPI support without forcing a separate documentation platform

This path preserves optionality:

- narrative docs can stay repo-local and reviewable
- API reference can be generated from FastAPI's `openapi.json`
- if we later need a public-only docs deploy, the same content model can still be deployed separately

### Viable alternative: Sphinx with MyST

Choose Sphinx instead if the center of gravity shifts toward:

- Python package documentation
- heavier internal architecture docs
- docstring-driven API reference
- static-site-only delivery with minimal Next.js involvement

Sphinx is the right alternative when documentation should track the Python codebase more closely than the product UI.

### Not recommended as the default: Mintlify

Mintlify is credible, and OpenClaw's usage shows it works well for a polished external docs portal. It is not the best default here because it introduces a second platform and moves docs away from the current app/runtime, while this repo already has a strong Next.js surface that can host docs directly.

## Suggested next steps

### Option A: Smallest useful spike

Build a thin `/docs` section inside the existing Next.js app using Fumadocs and wire one generated API reference section from FastAPI's `openapi.json`.

This validates:

- content migration effort from `docs/*.md`
- route structure and nav model
- whether the OpenAPI experience is good enough without extra tooling

### Option B: Conservative fallback spike

Create a tiny `docs-site/` Sphinx project using MyST and render:

- one existing ops guide
- one architecture guide
- one API reference page from OpenAPI

This answers whether the team prefers Python-centric docs workflows.

### Option C: Decision shortcut

If the goal is simply to move fast and avoid over-research, choose:

- `Fumadocs` if docs should live with the app
- `Sphinx` if docs should live with the Python backend
- `Mintlify` only if an external hosted product-docs property is explicitly desired

## Implementation notes if we pick Fumadocs

Expected first-pass shape:

- keep narrative content under something like `content/docs/`
- add a `/docs` route group in the existing Next.js app
- fetch or snapshot FastAPI's OpenAPI schema during build
- generate API reference pages from the schema
- migrate high-value existing docs first:
  - `docs/fastapi-backend-rollout.md`

This keeps the change small and reversible.

## Sources

- Sphinx overview: [https://www.sphinx-doc.org/en/master/](https://www.sphinx-doc.org/en/master/)
- Sphinx autodoc: [https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html)
- Sphinx apidoc: [https://www.sphinx-doc.org/en/master/usage/extensions/apidoc.html](https://www.sphinx-doc.org/en/master/usage/extensions/apidoc.html)
- MyST for Sphinx: [https://myst-parser.readthedocs.io/](https://myst-parser.readthedocs.io/)
- Sphinx OpenAPI extension: [https://sphinxcontrib-openapi.readthedocs.io/](https://sphinxcontrib-openapi.readthedocs.io/)
- Next.js MDX guide: [https://nextjs.org/docs/app/guides/mdx](https://nextjs.org/docs/app/guides/mdx)
- Fumadocs overview: [https://fumadocs.dev/](https://fumadocs.dev/)
- Fumadocs OpenAPI integration: [https://www.fumadocs.dev/docs/integrations/openapi/server](https://www.fumadocs.dev/docs/integrations/openapi/server)
- Nextra docs theme: [https://nextra.site/docs/docs-theme/start](https://nextra.site/docs/docs-theme/start)
- OpenClaw docs site: [https://docs.openclaw.ai/](https://docs.openclaw.ai/)
- Mintlify API playground/OpenAPI docs: [https://mintlify.com/docs/api-playground](https://mintlify.com/docs/api-playground)
