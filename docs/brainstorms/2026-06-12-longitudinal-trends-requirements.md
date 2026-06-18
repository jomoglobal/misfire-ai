# MisfireAI — Longitudinal Vehicle Intelligence (Trends)

**Created:** 2026-06-12
**Status:** Ready for planning
**Supersedes:** `2026-06-12-consumer-ux-reframe-requirements.md` is paused pending this — the UX reframe should be designed to accommodate the longitudinal vision, not just single-session analysis.

---

## Problem Frame

The current MisfireAI demo analyzes one driving session and produces a point-in-time health report. This is useful, but it misses the product's core differentiator: long-term vehicle intelligence.

A single OBD2 session tells you what your car was doing *that drive*. Three years of sessions tell you whether your fuel trims have been drifting for six months, whether knock retard gets worse every summer, whether a repair actually fixed anything, or whether a slow degradation is building toward a future failure — before it becomes one.

The existing project already has:
- **394 real MHD sessions from a 2009 BMW 335i (IJE0S), spanning 2023–2026** — 3 years of personal vehicle history
- A `SessionRecord` schema and SQLite store for multi-session data
- A `/api/trends/{vehicle_id}/{pid}` endpoint returning per-PID time series
- A Trends tab in the UI (currently empty in the Railway demo because the DB is ephemeral)

The gap: the demo doesn't show this data, and the product doesn't yet have a UI that presents longitudinal analysis in a consumer-readable way.

---

## Product Vision

**Every driver should have a long-term AI datalogger that teaches them about their car.**

Most car problems don't appear suddenly — they develop over time, slowly, below the threshold of what a driver notices in a single drive. Fuel trim drift. Progressive knock retard. Cooling system degradation. A long-term data layer surfaces these patterns before they become breakdowns.

This is what makes MisfireAI different from a code reader: not "what's wrong today" but "what's been changing, and where is it heading."

---

## Target Audiences

| Priority | Audience | What they need |
|---|---|---|
| Primary | Investors / judges | See the product vision — "this is not a scan tool, it's a vehicle intelligence layer" |
| Primary | Everyday car owners | "My car has 3 years of history and the AI found something I never would have noticed" |
| Secondary | Fleet operators | Multi-vehicle trend monitoring across a managed fleet |

---

## Actors

- **A1 — Car owner with history:** Has accumulated multiple OBD2 sessions (via MHD, CarScanner, or continuous logger). Wants to understand how their car has changed over time.
- **A2 — Demo visitor / investor:** Has no data of their own. Needs to see a compelling pre-seeded example to understand the product story.
- **A3 — Fleet operator:** Manages multiple vehicles, each with growing session history. Wants to monitor fleet health trends without manual per-vehicle review.

---

## Core Insight: The Demo Must Work Without User Data

The biggest design constraint: most demo visitors have no OBD2 files. The longitudinal demo must work for A2 (investor, first-time visitor) using pre-seeded data — specifically the 394 BMW 335i sessions — while also being ready to show A1's own data if they have it.

---

## Key Flows

### F1 — Demo visitor sees the trend story (pre-seeded BMW data)
1. Visitor lands on demo.datronex.net
2. Runs the single-session BMW analysis (existing flow)
3. After the health report, a prompt appears: "This vehicle has 394 sessions in the MisfireAI history. See the full trend analysis →"
4. Visitor clicks through to the trend view
5. System displays the longitudinal analysis for bmw-335i-IJE0S using pre-seeded data
6. Trend view adapts to available data: AI narrative summary + health score timeline + per-system trend charts

### F2 — Car owner uploads their own history
1. Owner uploads multiple session files (batch upload)
2. System ingests all sessions and derives their vehicle's history
3. Trend view shows their car's longitudinal story
4. If limited data (< ~5 sessions), the system shows what's available and indicates what more sessions would reveal

### F3 — Investor reads the product pitch through the demo
1. Investor sees the single-session "instant diagnosis" — quick proof of technical capability
2. Clicks into the trend history — sees 3 years of real BMW data
3. AI narrative explains what changed and when: "Fuel trims shifted lean in Q3 2025 — consistent with the tune change recorded in session filenames"
4. Investor understands: this is not a scan tool, it's a learning system that knows your car

---

## Requirements

### Pre-seeded demo data
- **R1:** The 394 BMW 335i sessions (IJE0S, 2023–2026) are pre-processed and bundled as seed data for the Railway demo
- **R2:** Seed data populates on startup if the sessions table is empty — so Railway's ephemeral SQLite is populated fresh on every deploy
- **R3:** Seed data includes: session metadata (date, row count, PIDs), per-session health scores by system, and per-session PID summary stats (mean/std per signal per session)
- **R4:** The seed file lives in `data/sample/` and is committed to the repo (OBD2 telemetry is not personal data — confirmed safe for public repo)

### Entry point from single-session report
- **R5:** After a single-session analysis completes, if the vehicle has historical sessions, a clear prompt/button appears: "See [N] sessions of history for this vehicle →"
- **R6:** In demo mode, this always links to the BMW IJE0S history (the pre-seeded data)
- **R7:** The prompt is visually distinct but not dominant — it enhances the single-session result, doesn't replace it

### Trend view — adaptive presentation
- **R8:** The trend view adapts its depth to available data:
  - 1–4 sessions: basic comparison, note that more sessions reveal trends
  - 5–20 sessions: health score timeline + system comparison
  - 20+ sessions: full longitudinal view with AI narrative, drift detection, anomaly callouts
- **R9:** Health score timeline: line chart of overall health % by session date — the primary "did this car get better or worse?" view
- **R10:** Per-system trend cards: separate trend lines for Fuel System, Engine Cooling, Ignition, Catalytic Converter — each shows its trajectory over time
- **R11:** AI narrative summary: plain-language description of what the trend data shows — generated by GPT-4o against the aggregated session history, not repeated single-session analysis
- **R12:** Narrative adapts to data density: richer narrative with 100+ sessions, cautious/exploratory narrative with 5–20 sessions, "not enough data for trend analysis" with < 5 sessions

### Trend view — consumer language
- **R13:** No raw PID names in the trend view main body (LTFT_B1, STFT_B2 etc. are collapsed behind "Technical Details" as in the single-session report)
- **R14:** System names use consumer language: "Fuel System" not "fueling", "Engine Cooling" not "cooling"
- **R15:** The AI narrative uses plain language — same standard as the single-session COMPOUND output

### Session ingestion
- **R16:** Batch ingest endpoint accepts multiple files in one request (building on existing `ingest_batch` MCP tool)
- **R17:** Each ingested session stores: vehicle_id, recorded_at (from MHD filename or file mtime), health scores per system, PID summary stats
- **R18:** Duplicate sessions (same file, same vehicle, same timestamp) are handled gracefully — no double-counting

---

## Acceptance Examples

**AE1 — Investor reveal (A2):** An investor runs the BMW demo, sees the single-session health report, then clicks "See 394 sessions of history." The trend view loads and shows a health score timeline across 3 years. The AI narrative says something like: "Over 394 sessions, this vehicle's fuel system shows early lean drift in late 2025 consistent with a tune upgrade. Ignition health has been stable. Cooling system shows a gradual efficiency decline worth monitoring." The investor says "I get it — this is different from a code reader."

**AE2 — Car owner with 10 sessions (A1):** A car owner uploads 10 MHD files. The trend view shows 10 data points on a health score timeline with a note: "10 sessions analyzed. Trends become clearer with more data." The AI narrative identifies any notable changes across those 10 sessions without overstating confidence.

**AE3 — Adaptive depth:** A visitor with 2 sessions sees a basic comparison panel ("Session 1 vs. Session 2") and a message: "Upload more sessions to see long-term trends." They do not see empty charts or error states.

**AE4 — Plain language (A1/A2):** At no point in the trend view does a consumer see LTFT_B1, STFT_B2, or any raw PID name in the main body. They see "Fuel System: showing lean drift" and can expand Technical Details if they want the raw values.

---

## Scope Boundaries

### In scope
- Pre-seeded BMW demo data (394 sessions → seed file at startup)
- Entry point from single-session report to trend history
- Trend view with adaptive depth (AI narrative + health timeline + per-system trends)
- Consumer language throughout (no raw PID names in main body)
- Batch session ingestion for users who want to upload their own history

### Out of scope (deferred)
- Real-time continuous logging (Dragy / ESP32 hardware pipeline) — this is a future hardware product
- Multi-vehicle fleet dashboard — foundational trend work first, fleet aggregation later
- User accounts / authentication — demo is single-vehicle, no login needed
- Push alerts ("your fuel trims are drifting — check your car") — needs persistent user identity first
- Mobile app — web-first

### Open questions for planning
- What format should the seed data take? Options: (a) bundled SQLite DB file committed to repo, (b) JSON/CSV seed file that the app ingests on startup, (c) pre-computed JSON blob served statically. Each has different tradeoffs for Railway deploy speed and repo size.
- Should the AI narrative for long-term trends use a new prompt, or extend the existing `system_prompt_v2.txt`?
- The 394 BMW session files — are they already pre-processed (health scores computed) or does the seed-generation step need to run the full pipeline on each?

---

## Relationship to Consumer UX Reframe

The `2026-06-12-consumer-ux-reframe-requirements.md` doc (doctor's visit report card) is paused pending this one. When the UX reframe is resumed, it should be designed with the longitudinal flow in mind:

- The single-session report is the **entry point**, not the destination
- The report should naturally lead into the trend history if session data exists
- The "doctor's visit" metaphor extends naturally: one visit is a snapshot; a long patient history is where patterns emerge
