# ADR-0001: UI framework for the production Running Records app

## Status

**Accepted** — conditional/phased decision (see [Decision](#decision)). Supersede
with a follow-up ADR once the production scale is chosen and a framework is
committed.

## Date

2026-06-18

## Context

Running Records is a Streamlit app that records a student reading aloud,
transcribes it with Whisper (`openai/whisper-medium`), aligns the transcript
against a target passage, and reports miscues to a teacher dashboard. It works
end-to-end today, but it is heading toward a "production" deployment whose
**target scale is not yet decided**.

Three hard requirements are already known for the production UI:

1. **Authentication & multi-user accounts** — login, teacher/admin roles, and
   per-user data isolation.
2. **Mobile / tablet friendly** — teachers running assessments on iPads in
   classrooms; touch-first, responsive.
3. **Self-hosted / offline capable** — able to run on a school's own network
   with student data staying on-prem.

Two app-specific characteristics also shape the choice:

- **In-browser audio capture** — the app records the student in the browser
  (currently `st.audio_input`).
- **Heavy server-side ASR** — Whisper inference is CPU/GPU-bound and takes
  seconds per reading, so the UI framework's **concurrency model matters** (a
  long transcription must not block other users' sessions).

This ADR evaluates whether Streamlit is the right production UI framework and,
if not, which alternatives to consider. It deliberately does **not** force a
single end-state, because the scale decision (single school vs. district SaaS
vs. commercial) changes the answer. Instead it commits to the parts that are
correct under every scenario and lays out a scale-triggered path.

### Current architecture note

The ASR/alignment **core already lives under `src/`** (`pipeline.py`,
`alignment.py`, `models.py`), but orchestration, persistence, passages handling,
and config are currently embedded in the Streamlit pages. A parallel refactor
(Track A1) extracts a UI-agnostic core (`src/config.py`, `src/passages.py`,
`src/storage.py`, `src/assessment.py`). **That decoupling is the key enabler for
this decision**: once the UI is a thin layer over a tested core, changing
frameworks becomes a UI-only swap rather than a rewrite.

## Decision

1. **Decouple the core from Streamlit now** (Track A1), regardless of the
   eventual framework. This is the highest-leverage, lowest-regret move.
2. **Keep Streamlit as the current/MVP and "internal tool" UI.** It is the
   fastest way to keep delivering and is a fine fit for a single-school /
   internal deployment.
3. **Adopt a decoupled `FastAPI` backend (wrapping the `src/` core) with either
   `HTMX` or a `Next.js`/React frontend when the production triggers are hit**
   (see [Triggers to revisit](#triggers-to-revisit)). Lead recommendation for a
   Python-first team is **FastAPI + HTMX**; choose **FastAPI + Next.js** if
   mobile-first/PWA polish and a richer SPA are required and JS/TS skills are
   available.

This is a phased decision: do (1) immediately, run on (2), and move to (3) when
scale demands it.

## Requirements → evaluation criteria (weighted)

| # | Criterion | Weight | Why |
|---|---|---|---|
| 1 | Auth & multi-user / RBAC | 5 | Hard requirement |
| 2 | Mobile / tablet UX | 5 | Hard requirement |
| 3 | Self-host / offline (on-prem) | 4 | Hard requirement |
| 4 | In-browser audio capture | 4 | Core app interaction |
| 5 | Concurrency/scaling under heavy ASR | 4 | Long transcriptions must not block users |
| 6 | Dev velocity / time-to-ship | 3 | Small team, evolving product |
| 7 | Python-first / team-skill fit | 4 | Team is Python-centric |
| 8 | Design customizability | 3 | Branding, custom components |
| 9 | Ecosystem maturity / stability | 3 | Production risk |
| 10 | UI testability | 2 | Regression safety |
| 11 | Migration cost from current Streamlit | 3 | Effort to get there |

Scores are 1 (poor) – 5 (excellent). Weighted total max = 200.

## Candidates scored

| Criterion (weight) | Streamlit | Gradio | Reflex | NiceGUI | Dash | FastAPI+HTMX | FastAPI+Next.js |
|---|---|---|---|---|---|---|---|
| Auth/RBAC (5) | 2 | 2 | 4 | 3 | 3 | 5 | 5 |
| Mobile/tablet (5) | 2 | 3 | 4 | 4 | 3 | 4 | 5 |
| Self-host/offline (4) | 4 | 4 | 4 | 4 | 4 | 5 | 4 |
| Audio capture (4) | 4 | 5 | 3 | 3 | 2 | 4 | 5 |
| Concurrency/ASR (4) | 2 | 3 | 4 | 4 | 4 | 5 | 5 |
| Dev velocity (3) | 5 | 5 | 3 | 4 | 3 | 3 | 2 |
| Python-first (4) | 5 | 5 | 5 | 5 | 5 | 4 | 2 |
| Customizability (3) | 2 | 2 | 4 | 4 | 4 | 5 | 5 |
| Maturity (3) | 4 | 4 | 3 | 3 | 5 | 5 | 5 |
| Testability (2) | 2 | 2 | 3 | 3 | 3 | 4 | 5 |
| Migration cost (3) | 5 | 3 | 3 | 3 | 3 | 2 | 1 |
| **Weighted total** | **132** | **139** | **149** | **147** | **141** | **170** | **163** |

The production-weighted ranking is **FastAPI+HTMX (170) > FastAPI+Next.js (163) >
Reflex (149) > NiceGUI (147) > Dash (141) > Gradio (139) > Streamlit (132)**.

Streamlit ranks last on this *production-weighted* matrix precisely because the
heavy weights sit on its weakest axes (auth, mobile, concurrency,
customizability). But note its standout cells: **dev velocity 5** and
**migration cost 5** — which is why it remains the right choice for the
MVP/internal scenario, where those weights dominate instead.

## Alternatives considered (rationale)

### Streamlit (baseline / incumbent)
- **Pros:** Zero web-dev required; fastest iteration; mature (Snowflake-backed);
  `st.audio_input` already gives us in-browser capture; self-hosts trivially.
- **Cons:** Native auth (`st.login`, ≥1.42) provides OIDC **authentication but
  not authorization** — no roles/RBAC or per-tenant isolation; real deployments
  front it with an auth proxy. The rerun-the-whole-script model with one
  WebSocket session per user scales poorly for long, blocking ASR calls and
  highly interactive flows. Limited design control; UI is hard to test.
- **Verdict:** Excellent MVP/internal tool; weak fit for multi-tenant SaaS.

### Gradio
- **Pros:** Best-in-class audio components; HF-backed; built-in request queue
  handles ML workloads better than Streamlit; pure Python.
- **Cons:** Even more demo-oriented; weak multi-page/app structure; only basic
  auth; limited customization.
- **Rejected as the production UI:** strengths are ML-demo UX, not a multi-user
  product; not a meaningful upgrade over Streamlit for our app-style needs.

### Reflex
- **Pros:** Pure Python that compiles to a React frontend + FastAPI backend;
  real routing/components/state; good customization and mobile potential;
  improving fast (v0.8).
- **Cons:** Younger ecosystem (v0.x); requires a Node build step and some
  web-dev concepts; audio recording needs a custom component.
- **Rejected (for now):** strong contender, but a less mature bet than a plain
  FastAPI backend; revisit if we want pure-Python full-stack.

### NiceGUI
- **Pros:** FastAPI-based; Vue/Quasar components are genuinely mobile-friendly;
  app-style UIs (forms/admin) fit a teacher dashboard; pure Python; quick.
- **Cons:** Smaller community; weaker docs; audio capture needs custom JS;
  long-term API stability less proven than FastAPI/React.
- **Rejected (for now):** good middle option; the FastAPI+HTMX path gets similar
  benefits on a more standard, better-documented stack.

### Dash (Plotly)
- **Pros:** Very mature; enterprise pedigree; scales on Flask/WSGI; strong for
  data-heavy dashboards.
- **Cons:** Callback-heavy boilerplate; no native audio capture; auth is basic
  unless on Dash Enterprise; mobile is average.
- **Rejected:** weakest on our audio-capture need; ergonomics don't justify it
  over FastAPI.

### FastAPI + HTMX  ⭐ lead recommendation for production
- **Pros:** Full control over auth (sessions/JWT/OIDC + real RBAC and
  multi-tenant isolation); async backend with background tasks/queues purpose-built
  for offloading heavy Whisper jobs; server-rendered responsive HTML (+ Tailwind)
  is excellent on tablets; self-hosts cleanly; **stays Python-first** with only
  light HTML/HTMX and minimal JS; the `src/` core drops straight in behind it.
- **Cons:** More code than Streamlit; in-browser recording uses the
  `MediaRecorder` API + an upload endpoint (a small, well-trodden amount of JS);
  highest migration effort alongside Next.js.
- **Verdict:** Best fit for the known hard constraints while preserving the
  Python-centric team and a single, simple stack.

### FastAPI + Next.js / React
- **Pros:** Maximum mobile-first/PWA polish; richest interactivity; first-class
  auth (Auth.js/Clerk/Keycloak); cleanly decoupled, independently scalable API
  and UI; best testability.
- **Cons:** Two codebases; needs JS/TS skill the team may not have; slowest to
  ship; largest migration.
- **Verdict:** The choice **if** the product becomes commercial/mobile-first and
  JS capacity exists; otherwise HTMX delivers most of the value for far less cost.

## Scenario-based recommendation

| Scenario | Recommended UI | Auth approach |
|---|---|---|
| **Single school / internal tool** | **Keep Streamlit** + finish refinements | `st.login` (OIDC) and/or reverse-proxy auth (oauth2-proxy) |
| **District / multi-school SaaS** | **FastAPI + HTMX** over the `src/` core | App-managed sessions/JWT + RBAC + per-tenant data isolation |
| **Commercial / mobile-first product** | **FastAPI + Next.js/React** | Auth.js / Clerk / Keycloak, PWA |

Under all three, **Track A1 decoupling is done first**, so the core is reused
unchanged and only the presentation layer differs.

## Consequences

- **Positive:** Decoupling pays off immediately (testable core, no duplicated
  passages/storage logic) and makes the eventual framework move incremental and
  low-risk. We keep shipping on Streamlit in the meantime with no dead-end.
- **Negative / cost:** A future migration to FastAPI-based UI is real work
  (rebuilding pages, adding a `MediaRecorder` capture component, wiring auth).
  Running Streamlit for multi-tenant in the interim still needs an auth proxy.
- **Operational:** Heavy ASR should move to a background worker/queue in any
  production stack so transcription never blocks request handling; this is far
  easier on FastAPI than on Streamlit.

## Triggers to revisit (move off Streamlit)

Adopt the FastAPI-based path when any of these become true:

- More than a handful of **concurrent** assessments, or noticeable session
  blocking during transcription.
- **External users / multiple tenants** requiring real RBAC and data isolation.
- **Tablet-first** classroom use where Streamlit's layout proves inadequate.
- Need for **custom branding**, an app-store/PWA presence, or billing.
- Compliance requirements (student data: FERPA/COPPA) that demand hardened,
  audited auth beyond a proxy.

## References

- [st.login — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/user/st.login)
- [User authentication and information — Streamlit Docs](https://docs.streamlit.io/develop/concepts/connections/authentication)
- [Native authentication support for Streamlit — issue #8518](https://github.com/streamlit/streamlit/issues/8518)
- [Reflex vs Streamlit — framework comparison](https://reflex.dev/blog/reflex-streamlit/)
- [Streamlit vs. NiceGUI — Bitdoze](https://www.bitdoze.com/streamlit-vs-nicegui/)
- [A quick comparison: Streamlit, Dash, Reflex and Rio — DEV](https://dev.to/sn3llius/a-quick-comparison-streamlit-dash-reflex-and-rio-57gf)
