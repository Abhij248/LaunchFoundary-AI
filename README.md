# LaunchFoundry AI

An AI-powered business builder: a business owner describes their business (and optionally uploads photos/menus/flyers), and the system researches it, reasons about what the business actually needs, and generates a real, live, standalone website — with working ordering/booking/lead workflows, real backend persistence, and an ongoing dashboard the owner can use to manage items, pricing, and request fixes, without touching code.

It is not a static template picker. Every generated site is produced by an LLM (xAI's Grok) working from real research and real business facts, with just enough structure enforced (a small integration contract, described in words, not prescribed markup) to keep it wired into a real backend.

## Two surfaces

The product is split into two distinct experiences, both served from the same FastAPI app:

1. **The wizard** (`Intake → Reasoning → Build Spec → Website → QA`) — a one-time flow, gated behind login, that takes raw business facts (and optional uploaded images) and produces a live website. Once generation finishes, the owner is automatically handed into the dashboard.
2. **The dashboard** — the ongoing, persistent, per-owner view: a list of "my businesses," and for whichever one is selected: its live site link, an inline preview, real orders/bookings/leads, a menu/pricing editor, and a "Request a Fix" box for describing anything wrong or missing after the fact.

A third, implicit surface is the **generated site itself** — served directly at `/site/{slug}`, a real URL any customer can visit, independent of the builder tool.

## Data flow (end to end)

1. **Sign up / log in** (`auth_store.py`, cookie session) — required before the wizard is usable.
2. **Intake** — business name, location, goal, raw description, optional logo/asset images, brand colors.
3. **Asset extraction** (`/extract-assets`) — uploaded images are sent to Grok's vision model (`get_vision_config()` in `agentic_planner.py`) to pull out menu items, prices, services, contact details, and visual cues.
4. **BuildSpec generation** (`/generate-buildspec-stream`) — runs two independent pipelines in parallel (see [Two pipelines](#two-pipelines) below) and can pause mid-graph to ask the owner clarifying questions (human-in-the-loop) when real operational gaps are detected (e.g. missing prices for extracted items).
5. **Research** (`/run-research`, `research_agents.py`) — competitor analysis, local SEO keyword research, and menu/service extraction, all fed into the generation prompt so copy reflects real findings instead of generic filler.
6. **Website generation** (`/generate-code`, `code_generator.py`) — the deterministic BuildSpec plus all research/reasoning context is turned into one prompt. Grok is given creative freedom over layout/CSS/JS/imagery, told in plain English what workflows the business needs (cart, one-click reserve, lead forms), and given exactly one hard requirement: report completed orders/reservations/leads to the business's own backend via a same-origin `fetch(...)` call.
7. **Persistence** (`menu_store.py`, `submissions_store.py`) — on first generation, a business record is created (with a public slug and a durable business ID) and any extracted menu/catalog items are seeded into a real SQLite-backed items table. The exact BuildSpec used is stored too, so later revisions have real context.
8. **Live site** (`GET /site/{slug}`) — serves the stored HTML directly to any visitor. That page fetches its current item list and posts real submissions to the backend — it does not depend on the builder tool being open.
9. **Owner dashboard** — the owner edits items/prices (`PUT /businesses/{id}/items`, whole-list replace) and sees real orders/bookings/leads (`GET /businesses/{id}/submissions`), both persisted, both visible across sessions and devices.
10. **Request a Fix** (`POST /businesses/{id}/revise`) — since a single LLM generation won't always get everything right, the owner can describe what's wrong or missing (e.g. "menu and tickets are mixed together") and get a *targeted* revision of the live page, built from the stored BuildSpec + current HTML + the request. The revision only replaces the live site if it passes the same acceptance check fresh generations do — otherwise the current site is left untouched.

## Two pipelines

`/generate-buildspec-stream` runs two pipelines on every request that don't talk to each other:

- **Track A — deterministic** (`buildspec_planner.py`): pure Python, no LLM calls, no Pydantic validation. Classifies the business into a vertical + one of five transactional "shapes" (`storefront_commerce`, `scheduled_booking`, `inquiry_lead`, `portfolio_showcase`, `catalog_reserve`), selects features from a declarative registry, and produces the `BuildSpec` that actually drives `code_generator.py` and `deployment_system.py`. **This is the pipeline that matters for what gets built.**
- **Track B — LangGraph reasoning** (`agentic_graph.py`, 11 nodes: `business_profile → memory_retrieval → requirements → human_input → strategy_hypotheses → design_candidates → critique → reflection → debate → simulation → revise`): a slower, LLM-driven reasoning graph that classifies behavioral archetypes (`business_archetype_mapper.py`, `behavioral_*.py`), retrieves similar-business "lessons" from a curated memory bank (`agentic_memory.py`), simulates the design, and runs a multi-agent critique/debate loop. Its output is streamed to the frontend as a live timeline (the "watch the agents think" view) and forwarded into the generation prompt as extra reasoning notes — it does not independently decide pages/sections the way Track A does.

## Tech stack

- **Backend**: Python, FastAPI, Uvicorn. No ORM — hand-written SQLite via stdlib `sqlite3`.
- **LLM provider**: xAI (Grok), via a small multi-provider abstraction in `agentic_planner.py` (`PROVIDER_CONFIG`, currently `xai` and a legacy `pollinations` fallback). Cheap/fast JSON-extraction calls use one model; the final HTML generation and revision calls use a separately-configured "best" model with its own `reasoning_effort` setting, since generation benefits from a stronger model while routine classification doesn't need it.
- **Vision**: Grok's vision model, for extracting structured business info from uploaded images.
- **Agent orchestration**: LangGraph, for the Track B reasoning graph.
- **Auth**: stdlib `hashlib.scrypt` (salted password hashing, no bcrypt/passlib dependency) + server-side session tokens in an HttpOnly cookie. No third-party auth provider.
- **Persistence**: SQLite, one file, stored at `~/.launchfoundry/menu_items.db` — **deliberately outside the repo**, since the app mounts the whole repo root as public static files (`/static/...`); a DB file inside the repo would be publicly downloadable.
- **Frontend**: vanilla HTML/CSS/JS. No framework, no bundler, no build step — `app.js` is loaded directly by `index.html`.

## Database schema

All tables live in the single SQLite file (`menu_store.DB_PATH`), split across three modules by concern:

| Table | Module | Purpose |
|---|---|---|
| `businesses` | `menu_store.py` | One row per generated business: `business_id`, `owner_id` (nullable — set on first login-linked generation), `name`, unique public `slug`, `html_preview` (the live site's current HTML), `build_spec_json` (context for revisions), timestamps. |
| `menu_items` | `menu_store.py` | Owner-editable catalog items, keyed on `(business_id, id)` so the same item id can't collide across different businesses. `{name, category, description, price_label, price_sort_value, sort_order}`. |
| `business_meta` | `menu_store.py` | One row per business: `seeded_at`. Guards against re-seeding items from stale generation-time data after the owner has already edited/deleted them. |
| `owners` | `auth_store.py` | `owner_id`, unique `email`, `password_hash` (scrypt). |
| `sessions` | `auth_store.py` | Session tokens (30-day expiry) mapping to an `owner_id`. |
| `submissions` | `submissions_store.py` | Real customer activity: `type` (`order`/`reservation`/`lead`), `customer`, `summary`, `contact`, `created_at`, scoped to `business_id`. This is what the dashboard's Orders/Bookings/Leads panels actually read from. |

## Key modules

**Core generation pipeline**
| File | Responsibility |
|---|---|
| `amd_inference_server.py` | FastAPI app: every HTTP route, request/response wiring. |
| `buildspec_planner.py` | Track A: deterministic vertical/shape classification, feature selection, the declarative `FEATURE_REGISTRY`. |
| `code_generator.py` | Builds the LLM generation/revision prompt, calls the model, runs the acceptance gate, and the deterministic fallback template. |
| `deployment_system.py` | Generates the downloadable "deployment package" (DB schema doc, docker-compose, auth/payment config, README) for owners who want to self-host elsewhere. |
| `critique_system.py` | Five specialist critique agents (UX, accessibility, conversion, security, performance) that review generated code. |
| `agentic_planner.py` | Multi-provider LLM client abstraction (`ModelJsonPlanner`) — model selection, retries, JSON parsing. |

**Track B — LangGraph reasoning**
| File | Responsibility |
|---|---|
| `agentic_graph.py` | The LangGraph state machine itself: all 11 nodes, routing logic, human-in-the-loop pausing. |
| `agentic_models.py` | Pydantic models for graph state (`Vertical`, `StrategyHypothesis`, `DebateOutcome`, etc.). |
| `agentic_memory.py` | Retrieves relevant "lessons" from a curated memory bank based on business archetype/evidence tags. |
| `agentic_cognition_tools.py` | Structured context tools fed into reasoning prompts (business snapshot, asset evidence, memory guidance, process health, etc.). |
| `agentic_external_tools.py` | Web search / page reading / design-quality tools used by research and critique. |
| `business_archetype_mapper.py`, `behavioral_*.py` | Classify a business into behavioral archetypes (e.g. `fast_impulse_conversion`, `high_trust_consideration`) and derive visual/priority decisions from them. |
| `vertical_rulebooks.py` | Hand-authored per-vertical rules consumed by the requirements stage. |
| `research_agents.py` | Competitor analysis, local SEO, and menu/service extraction research agents. |

**Persistence**
| File | Responsibility |
|---|---|
| `menu_store.py` | Businesses + menu items (see schema above). |
| `auth_store.py` | Owners + sessions, password hashing. |
| `submissions_store.py` | Customer order/reservation/lead records. |

**Frontend**
| File | Responsibility |
|---|---|
| `index.html` | All markup for both surfaces (wizard panels + dashboard) plus the auth bar. |
| `app.js` | All client-side logic: pipeline orchestration, view-mode switching, dashboard rendering, menu editor, revision requests. |
| `styles.css` | The builder tool's own design system (not the generated customer sites, which are styled independently by the model each time). |

## API reference

| Route | Purpose |
|---|---|
| `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | Owner authentication, session-cookie based. |
| `GET /auth/my-businesses` | List businesses owned by the logged-in owner. |
| `POST /extract-assets` | Vision-extract structured info from uploaded images. |
| `POST /generate-buildspec`, `POST /generate-buildspec-stream` | Run Track A + Track B, streaming graph events (SSE) and pausing for human input when needed. |
| `POST /run-research` | Competitor/SEO/menu research agents. |
| `POST /generate-code` | Generate (or seed) a business's live website. |
| `POST /businesses/{id}/revise` | Targeted fix/change to an already-live page; keeps the old page if the revision doesn't pass validation. |
| `GET /site/{slug}` | The real, standalone customer-facing site. |
| `GET`/`PUT /businesses/{id}/items` | Owner's menu/catalog editor (whole-list read/replace). |
| `POST`/`GET /businesses/{id}/submissions` | Called by a generated site when a visitor completes an order/reservation/lead; read by the dashboard. |
| `POST /run-critique` | Multi-agent critique/debate on generated code. |
| `POST /generate-deployment` | Downloadable self-hosting package. |

## Running locally

```bash
pip install -r requirements-amd-server.txt
```

Create a `.env` file in the project root:

```
XAI_API_KEY=your-xai-key-here
```

(`agentic_planner.py` also supports a `pollinations` provider as a fallback if no xAI key is present, and per-role model overrides via `XAI_TEXT_MODEL` / `XAI_BEST_MODEL` / `XAI_VISION_MODEL`.)

Start the server:

```bash
python -m uvicorn amd_inference_server:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000`.

> **Windows note**: uvicorn's `--reload` occasionally hangs mid-restart on Windows (a known multiprocessing/StatReload quirk, not an app bug) — if changes stop taking effect, check for a stuck reloader process and do a full kill + restart.

## Known limitations (deliberate, not oversights)

- **No per-item CRUD** — the menu/catalog editor replaces the whole item list on save, not individual rows. Fine at menu-list scale with a single owner; would need real diffing for concurrent multi-editor use.
- **No authorization enforcement on business-scoped endpoints** — a `business_id` is an unguessable UUID, which is the only thing gating access to its items/submissions today. There's no server-side check that the logged-in owner actually owns the business_id they're calling with.
- **The deterministic fallback template doesn't support revisions or live item fetching** — it's a rare safety net used only when the LLM call itself fails, and intentionally has a smaller feature set than the primary LLM-generated path.
- **No migrations framework** — schema changes are additive, applied idempotently (`CREATE TABLE IF NOT EXISTS`, guarded `ALTER TABLE ADD COLUMN`) on every connection.
- **A single generation attempt is probabilistic** — the model doesn't always perfectly implement every required mechanism (e.g. the live-items fetch) on the first try. The acceptance gate catches this and logs it, but currently still ships the page rather than blocking it — "Request a Fix" from the dashboard is the intended correction path.

## Project history

This started as an AMD Developer Cloud / ROCm hackathon prototype (see the original `amd_gpu_buildspec_starter.ipynb` and `requirements-amd*.txt` files) using Pollinations.ai for inference. It has since moved to xAI's Grok models for both text and vision, and grown from a single-shot demo generator into a full product: real accounts, real persistence, a real customer-facing site per business, and an iterative correction loop — the AMD/ROCm and Pollinations references that remain in some filenames are historical, not part of the live inference path.
