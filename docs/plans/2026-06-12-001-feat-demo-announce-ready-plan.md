---
title: "feat: Demo announce-ready — trend history, pitch copy, plain-English stage names"
status: completed
created: 2026-06-12
origin:
  - docs/brainstorms/2026-06-12-longitudinal-trends-requirements.md
  - docs/brainstorms/2026-06-12-consumer-ux-reframe-requirements.md
---

## Summary

Three things must ship before the LinkedIn announcement:

1. **Trend history** — 618 BMW 335i MHD sessions (2023–2025) pre-processed into a JSON seed file, loaded at Railway startup, visible as a longitudinal health timeline + per-system trend charts + AI narrative. Entry point from the single-session report: "See N sessions of history →" button.
2. **Pitch copy above the fold** — a one-line product description so cold visitors immediately understand what MisfireAI is before clicking anything.
3. **Plain-English stage labels** — CATCH / ENRICH / SEPARATE / COMPOUND replaced in all visible UI; internal SSE wire names unchanged.

These three changes are independently shippable in dependency order: U1 (seed data) → U2 (startup loader + API) → U3 (trend view UI) → U4 (history entry point) → U5 (pitch copy) → U6 (stage labels). U5 and U6 have no dependencies and can ship any time.

---

## Problem Frame

The demo at demo.datronex.net works (single-session analysis runs end-to-end as of 2026-06-12), but it doesn't yet show MisfireAI's core differentiator: long-term vehicle intelligence. The Railway ephemeral filesystem means the SQLite DB empties on every deploy, so the existing Trends tab always loads empty. Stage labels are academic vocabulary from the IAI09 lab. There is no pitch copy to orient a cold visitor.

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Seed format | JSON file at `data/sample/bmw-ije0s-seed.json`, committed to repo | Inspectable, diffable, git-safe; SQLite binary is not. Loaded into SQLite at startup by new `_seed_db_if_empty()` function |
| Seed scope | All processable sessions from the 618 BMW CSV files in `Documents/Vehicles/2009 bmw 335i/datalogs/` | Full history is the demo's credibility claim; curated subsets undermine it |
| Health scores in seed | Seed script calls `score_vehicle_health()` per session | `ingest_batch` doesn't run scoring; health timeline requires per-session `overall_score` and `system_scores` |
| Startup hook | Module-level call to `_seed_db_if_empty()` at bottom of `app.py`, after app and routes are defined | No lifespan API exists; module-level fires once at import, before first request |
| Trend API | New `/api/trends/{vehicle_id}/health` endpoint returning `[{recorded_at, overall_score, system_scores}]` | Existing `/api/trends/{vid}/{pid}` returns single-PID stats; health timeline needs scores, not raw PID means |
| AI trend narrative | New `/api/trends/{vehicle_id}/narrative` endpoint, one GPT-4o call per vehicle per cold-load (cached in-process) | Not called at startup; fires only when visitor views trend panel; same cost as single-session analysis |
| Stage label mapping | CATCH→"Read Data", ENRICH→"Identify Vehicle", SEPARATE→"Score Systems", COMPOUND→"AI Report" | Descriptive of what the step does for the user, not internal implementation vocabulary |
| Consumer UX full reframe | Deferred | Full results-layout restructuring (unified report card, rotating loading messages) is out of scope for this milestone — label rename + pitch copy are the minimum needed to announce |
| SSE wire protocol | Unchanged | Internal `stage: "catch"` etc. event names are not renamed — UI rendering layer only |

---

## High-Level Technical Design

*This illustrates the intended approach and is directional guidance for review, not implementation specification.*

```
Local machine (one-time):
  scripts/generate_seed.py
    ├── glob 618 CSVs from Windows datalogs path
    ├── for each: ingest_file() → score_vehicle_health()
    ├── build SessionRecord with overall_score + system_scores
    └── write data/sample/bmw-ije0s-seed.json

Railway deploy (every startup):
  app.py module load
    └── _seed_db_if_empty(SESSION_DB, "data/sample/bmw-ije0s-seed.json")
          └── if sessions table empty → bulk INSERT from JSON

Visitor flow:
  GET /               → demo page (VIN pre-filled)
  POST /api/analyze   → 4-stage pipeline → single-session report
  [button click]      → switchTab('trends') + loadVehicleHistory('IJE0S')
  GET /api/trends/IJE0S/health    → [{recorded_at, overall_score, system_scores}]
  GET /api/trends/IJE0S/narrative → {narrative: "..."} (GPT-4o, cached)
  [render]            → health timeline chart + per-system cards + AI narrative
```

---

## Scope Boundaries

### In scope
- Seed generation script (local, one-time run)
- Startup DB seeding at Railway deploy
- `/api/trends/{vehicle_id}/health` endpoint
- `/api/trends/{vehicle_id}/narrative` endpoint (GPT-4o, in-process cache)
- Trend view UI: health score timeline, per-system trend cards, AI narrative panel
- "See N sessions of history →" entry point after single-session report
- Pitch copy tagline above VIN input
- Stage label rename (progress bar + panel titles): 8 string changes in `_UI_HTML`
- Email label: "Owner Email (for HITL approval)" → "Email (optional — receive your report)"
- Badge: "OBD2 DEMO" → "Live Demo"
- Browser tab title: "MisfireAI — OBD2 Diagnostic Pipeline" → "MisfireAI — Vehicle Health"
- Drop hint: "MHD · CarScanner · CarOBD · CephaSAX · iSay Gerard" → "Upload your OBD2 data file"

### Deferred to follow-up work
- Full results-layout restructuring (unified report card, rotating loading messages) — see `docs/brainstorms/2026-06-12-consumer-ux-reframe-requirements.md`
- Consumer urgency label translations (NORMAL → "All Clear" etc.)
- Multi-vehicle fleet trend dashboard
- User accounts / persistent identity
- Mobile layout

### Out of scope
- Backend pipeline changes — what data is produced is unchanged
- SSE wire protocol rename
- Hardware logging pipeline (Dragy, ESP32)

---

## Implementation Units

### U1. Seed generation script

**Goal:** Run locally once against the 618 BMW CSV files, produce `data/sample/bmw-ije0s-seed.json` containing one SessionRecord-equivalent dict per successfully processed session (with health scores), commit the file.

**Requirements:** R1, R2, R3, R4 (see origin: `docs/brainstorms/2026-06-12-longitudinal-trends-requirements.md`)

**Dependencies:** None — prerequisite for all other units

**Files:**
- `scripts/generate_seed.py` — new script (create)
- `data/sample/bmw-ije0s-seed.json` — output artifact (create, commit)

**Approach:**
- Script accepts a `--datalogs-dir` argument pointing at the Windows datalogs folder (accessible via `/mnt/c/Users/GLOBAL_HP/Documents/Vehicles/2009 bmw 335i/datalogs/`)
- Globs all `*.csv` recursively; skips files under 5 rows (incomplete sessions) and files that fail parsing
- Per file: calls `ingest_file()` from `tools/mcp_server.py`, then `score_vehicle_health()` with the resulting pid_stats snapshot
- Constructs a dict matching `SessionRecord` field names; sets `file_path` to empty string (Windows path not valid on Railway), `vehicle_id` to `"IJE0S"`, `source` to `"mhd"`
- Writes a JSON array to `data/sample/bmw-ije0s-seed.json`; prints progress (processed / skipped / errors)
- The script is idempotent: re-running overwrites the seed file

**Patterns to follow:** `tools/mcp_server.py` `ingest_file()` and `score_vehicle_health()` are the authoritative implementations to call, not re-implement

**Test scenarios:**
- Happy path: script runs against the datalogs folder, produces a JSON file with N > 100 entries, each having a non-null `overall_score`, a non-empty `pid_stats`, and a valid ISO 8601 `recorded_at`
- Edge: files with < 5 rows are skipped and counted in the "skipped" summary; no error raised
- Edge: files that fail `ingest_file()` are caught, logged to stderr, and counted in "errors"; script continues to next file
- Edge: re-running the script overwrites the existing seed file without error
- Spot-check: open the JSON in a text editor and verify a mid-2024 session has recognizable MHD PID names (LTFT_B1, BOOST_ACTUAL, etc.) and a plausible overall_score (0.5–0.95)

**Verification:** `data/sample/bmw-ije0s-seed.json` exists, contains 300+ entries (filtering out short sessions from 618 raw), each entry has `overall_score` not null, `system_scores` dict not empty, `recorded_at` parseable as ISO 8601. File size between 3 MB and 20 MB.

---

### U2. Startup DB seeder + health trend API endpoints

**Goal:** On Railway startup, if the sessions table is empty, load `data/sample/bmw-ije0s-seed.json` into SQLite. Add two new GET endpoints for health timeline and AI trend narrative.

**Requirements:** R1, R2, R3 (longitudinal trends origin)

**Dependencies:** U1 (seed file must exist before this code runs in production)

**Files:**
- `app.py` — add `_seed_db_if_empty()` function + module-level call + two new route handlers
- `tools/session_store.py` — add `get_health_trend(vehicle_id, limit)` query method

**Approach:**

*Startup seeder (`_seed_db_if_empty`):*
- Called at module level near the bottom of `app.py`, after all route definitions
- Opens `SessionDB`, queries `SELECT COUNT(*) FROM sessions WHERE vehicle_id = 'IJE0S'`
- If count is 0 and the seed file exists: bulk-inserts all records using `SessionStore.save()` in a loop (or a single `executemany` for speed)
- Logs: "Seeded N sessions from bmw-ije0s-seed.json" or "Seed file not found — skipping" — never raises

*`GET /api/trends/{vehicle_id}/health`:*
- Calls `store.get_health_trend(vehicle_id, limit=500)`
- New `get_health_trend` method on `SessionStore`: `SELECT recorded_at, overall_score, system_scores FROM sessions WHERE vehicle_id = ? AND overall_score IS NOT NULL ORDER BY recorded_at ASC LIMIT ?`
- Returns JSON array: `[{recorded_at, overall_score, system_scores: {fueling, cooling, ignition, catalyst}}]`
- System score keys are renamed in the response to consumer names: `fueling` → `fuel_system`, `cooling` → `engine_cooling`, `ignition` → `ignition`, `catalyst` → `catalytic_converter`

*`GET /api/trends/{vehicle_id}/narrative`:*
- In-process cache: `_narrative_cache: dict[str, str] = {}` module-level dict keyed by `vehicle_id`
- If cached: return immediately
- Otherwise: fetch last 500 health records, compute aggregate stats (mean/trend per system, session count, date range), call GPT-4o with a new prompt (see U3 for prompt spec) instructing a 2–3 paragraph plain-language narrative
- Cache the result in `_narrative_cache[vehicle_id]`
- Returns `{"vehicle_id": ..., "narrative": "...", "session_count": N, "date_range": {"earliest": ..., "latest": ...}}`
- If `OPENAI_API_KEY` is not set: returns `{"narrative": null, "error": "AI narrative unavailable — no API key configured"}`

**Patterns to follow:**
- Existing `/api/trends/{vehicle_id}/{pid}` endpoint pattern in `app.py` lines 650–654
- `SessionStore.get_trend()` in `tools/session_store.py` lines 258–287 for query pattern
- `run_diagnostic_agent()` in `pipeline/agent.py` for GPT-4o call pattern

**Test scenarios:**
- Happy path: `GET /api/trends/IJE0S/health` returns 300+ items, each with `recorded_at`, `overall_score` between 0 and 1, and `system_scores` dict with `fuel_system`, `engine_cooling`, `ignition`, `catalytic_converter` keys
- Happy path: `GET /api/trends/IJE0S/narrative` returns a JSON object with non-empty `narrative` string, `session_count` > 100, valid `date_range`
- Edge: calling `/health` for a vehicle with no sessions returns `[]` (not an error)
- Edge: calling `/narrative` for a vehicle with no sessions returns a graceful message, not a 500
- Integration: after a fresh Railway deploy (empty DB), `GET /api/vehicles` returns `IJE0S` with session_count > 100, confirming the seeder ran
- Caching: calling `/narrative` twice returns identical content without a second GPT-4o call (verify via response time or log)

**Verification:** After local `uvicorn app:app` startup with seed file present, `GET /api/trends/IJE0S/health` returns 300+ records. `GET /api/trends/IJE0S/narrative` returns a coherent plain-language paragraph about the BMW's health history. `/api/vehicles` shows IJE0S with correct session count.

---

### U3. Trend view UI — health timeline + per-system cards + AI narrative

**Goal:** Build the longitudinal trend panel visible when a user switches to the Trends tab or clicks the history entry point. Shows health score timeline, per-system trend cards, and AI narrative. Adapts depth to available data.

**Requirements:** R8–R15 (longitudinal trends origin)

**Dependencies:** U2 (endpoints must exist)

**Files:**
- `app.py` — replace / heavily extend the existing `#trendsView` HTML section and its JS (`loadTrend`, trend chart canvas renderer)

**Approach:**

*Layout (within existing `#trendsView`):*
```
[AI narrative panel — plain text, 2-3 paragraphs]
[Health score timeline — canvas line chart, date on X, 0-100% on Y]
[System trend grid — 4 cards: Fuel System / Engine Cooling / Ignition / Catalytic Converter]
  each card: sparkline (mini canvas) + current score % + trend arrow (↑ stable / ↓ declining)
[Session count + date range footer — "394 sessions · Feb 2023 – Jun 2025"]
```

*Data flow:*
1. `loadVehicleHistory(vehicleId)` fetches `/api/trends/{vehicleId}/health` and `/api/trends/{vehicleId}/narrative` in parallel
2. If `health` array length < 5: show "Not enough sessions for trend analysis — N sessions recorded" message; skip charts
3. If length 5–19: show health timeline + session count; skip per-system cards; narrative is "exploratory"
4. If length 20+: show full layout

*Health timeline chart:*
- Reuse the existing hand-drawn canvas chart pattern from `loadTrend()` — same approach, adapted for `overall_score` data
- X axis: `recorded_at` dates; Y axis: 0–100 (score × 100); line color matches urgency zone (green above 75, amber 50–75, red below 50)
- No dependency on Chart.js — keep the existing vanilla canvas approach

*Per-system trend cards:*
- Each card shows the last 20 data points as a sparkline (small canvas, no axes)
- Score shown as a percentage number, color-coded green/amber/red
- Trend arrow: compare last-5-session mean vs. prev-5-session mean; ↑ if improving, → if stable (< 3% change), ↓ if declining

*AI narrative panel:*
- Fetches `/api/trends/{vehicleId}/narrative`
- While loading: show "Analyzing [N] sessions..." text
- On success: render the narrative text as plain paragraphs (no markdown bolding — strip `**text**` to plain text)
- On error/null: show "AI narrative unavailable" in muted text — do not break the layout

*Adaptive depth table for implementer:*

| Session count | Show narrative | Show timeline | Show system cards |
|---|---|---|---|
| < 5 | No | No | No — show "not enough data" |
| 5–19 | Yes (exploratory) | Yes | No |
| 20–99 | Yes | Yes | Yes |
| 100+ | Yes (full depth) | Yes | Yes |

*Consumer language throughout:*
- System names in cards: "Fuel System", "Engine Cooling", "Ignition", "Catalytic Converter"
- No raw PID names visible anywhere in the trend view
- Footer: "N sessions · [earliest year] – [latest year]"

**Patterns to follow:**
- Existing canvas chart renderer in `loadTrend()` (~lines 2440–2507) for chart drawing approach
- `renderCompound()` for plain-text narrative rendering pattern (strip markdown, render as paragraphs)
- Existing CSS variables (`--green`, `--amber`, `--red`, `--muted`) for color coding

**Test scenarios:**
- Happy path (100+ sessions): narrative panel renders text, health timeline shows a visible line across 2+ years, four system cards appear with percentage scores and trend arrows
- Covers AE1: investor clicks trend view, sees "394 sessions · 2023 – 2025" footer and a health timeline spanning the full date range
- Covers AE4: no raw PID names (LTFT_B1, STFT_B2 etc.) visible anywhere in the trend view DOM
- Edge (< 5 sessions): "not enough data" message appears; no empty chart canvases rendered
- Edge (5–19 sessions): timeline renders, system cards do not, narrative shows exploratory language
- Edge (narrative API error): layout still renders with timeline and system cards; narrative area shows muted fallback text
- Edge: switching between Analyze and Trends tabs multiple times does not duplicate charts or narrative panels

**Verification:** With the seeded BMW data, switching to the Trends tab shows a health score timeline spanning 2023–2025 with 300+ data points, four system trend cards with non-zero scores, and a plain-language AI narrative paragraph. No internal acronyms visible.

---

### U4. History entry point from single-session report

**Goal:** After a single-session analysis completes, if the analyzed vehicle has historical sessions in the DB, show a contextual prompt linking to the trend view.

**Requirements:** R5, R6, R7 (longitudinal trends origin)

**Dependencies:** U2 (health endpoint must exist), U3 (trend view must be built)

**Files:**
- `app.py` — add history prompt rendering to the post-analysis flow in `_UI_HTML` JS

**Approach:**
- After `renderCompound()` completes (i.e., the `done` SSE event is handled), call `GET /api/trends/{vehicleId}/health?limit=1` to check session count
- If count > 0: inject a dismissable banner/card below the last panel:
  > "This vehicle has **N sessions** in MisfireAI history. [See full trend analysis →]"
- In demo mode, `vehicleId` for the history lookup is always `"IJE0S"` (the pre-seeded vehicle)
- Clicking "See full trend analysis →" calls `switchTab('trends')` and `loadVehicleHistory(vehicleId)`
- Banner is styled with the existing card/panel CSS — not a modal or overlay
- If count is 0: no banner shown; single-session report stands alone

**Patterns to follow:**
- `renderHistory()` in `app.py` for the existing history-check-then-render pattern
- `switchTab()` for tab navigation

**Test scenarios:**
- Covers AE1 / F1: after BMW demo analysis completes, banner appears with "394 sessions" count and a clickable link
- Happy path: clicking the link switches to Trends tab and shows the full history view
- Edge (demo mode): banner always points to IJE0S history regardless of which VIN was used
- Edge (no sessions): no banner appears after analysis for a vehicle with no history

**Verification:** Run the demo analysis; banner appears below the AI Report panel with a session count > 100 and a working link to the trend view.

---

### U5. Pitch copy above the fold

**Goal:** Add a one-line product description above the VIN input field so a cold visitor understands what MisfireAI does before interacting.

**Requirements:** Pitch copy requirement (see origin: `docs/brainstorms/2026-06-12-consumer-ux-reframe-requirements.md` AE1)

**Dependencies:** None

**Files:**
- `app.py` — add tagline element to `_UI_HTML` sidebar HTML above the VIN input section

**Approach:**
- Add a short paragraph or subtitle element in the sidebar between the Options heading and the VIN field
- Copy (confirm or adjust during implementation): *"Upload your OBD2 data. Get a plain-language vehicle health report — backed by real AI analysis."*
- In demo mode this reads naturally since the VIN is pre-filled: visitor sees the tagline, then the pre-filled VIN, then the enabled Run Analysis button — the flow makes sense
- Styled as muted body text (use existing `--muted` CSS variable); not a hero headline
- No new CSS needed — use existing type styles

**Test scenarios:**
- Covers AE1: cold visitor lands on demo page; the tagline is visible above the VIN input before any interaction
- Edge (demo mode): tagline reads sensibly alongside the pre-filled VIN (does not refer to "upload" as the primary action)

**Verification:** Live page at demo.datronex.net shows the tagline text above the VIN field. A first-time visitor reading it can answer "what does this do?" without clicking anything.

---

### U6. Plain-English stage labels and copy cleanup

**Goal:** Replace all eight internal-vocabulary visible strings in the UI (4 progress bar labels + 4 panel titles) and clean up the remaining jargon copy (tab title, badge, email label, drop hint).

**Requirements:** Stage label rename (consumer-ux-reframe origin R14–R19); stage name mapping confirmed in Key Technical Decisions above.

**Dependencies:** None — isolated string changes, no behavioral impact

**Files:**
- `app.py` — 8 string changes in `_UI_HTML` for stage labels/titles + 5 copy cleanup changes

**Approach:**

String substitutions (all in `_UI_HTML`):

*Progress bar labels (lines ~1453, 1457, 1462, 1466):*
| Old | New |
|---|---|
| `CATCH` | `Read Data` |
| `ENRICH` | `Identify Vehicle` |
| `SEPARATE` | `Score Systems` |
| `COMPOUND` | `AI Report` |

*Panel title strings in JS render functions (lines ~1803, 1901, 1937, 1979):*
| Old | New |
|---|---|
| `CATCH &mdash; Signal Ingestion` | `Read Data &mdash; Signal Capture` |
| `ENRICH &mdash; Vehicle Metadata` | `Identify Vehicle &mdash; NHTSA Lookup` |
| `SEPARATE &mdash; System Health Scoring` | `Score Systems &mdash; Health Analysis` |
| `COMPOUND &mdash; AI Assessment` | `AI Report &mdash; Diagnostic Summary` |

*Surrounding copy cleanup:*
| Location | Old | New |
|---|---|---|
| `<title>` tag | `MisfireAI — OBD2 Diagnostic Pipeline` | `MisfireAI — Vehicle Health` |
| Demo badge (line ~1366) | `OBD2 DEMO` | `Live Demo` |
| Email label (line ~1415) | `Owner Email (for HITL approval)` | `Email (optional — receive your report)` |
| Drop hint (line ~1404) | `MHD · CarScanner · CarOBD · CephaSAX · iSay Gerard` | `Upload your OBD2 data file` |

*Do NOT rename:* `renderHITL()` panel title `HITL — Human-in-the-Loop` — this panel never shows in demo mode, so it's low priority and can be addressed in the full UX reframe.

**Test scenarios:**
- None of: CATCH, ENRICH, SEPARATE, COMPOUND, "Signal Ingestion", "HITL approval", "OBD2 Diagnostic Pipeline", "OBD2 DEMO" appear in the rendered page DOM (verify with browser devtools find-in-page or curl + grep)
- Progress bar shows "Read Data → Identify Vehicle → Score Systems → AI Report" during analysis
- Panel titles match the new strings after analysis completes
- Browser tab title reads "MisfireAI — Vehicle Health"

**Verification:** Run the demo analysis; no internal vocabulary visible anywhere in the UI. `curl -s https://demo.datronex.net/ | grep -c "CATCH\|ENRICH\|SEPARATE\|COMPOUND\|HITL approval\|OBD2 Diagnostic Pipeline\|OBD2 DEMO"` returns 0.

---

## Dependencies Diagram

```
U1 (seed script + data)
  └─→ U2 (startup seeder + API endpoints)
        └─→ U3 (trend view UI)
              └─→ U4 (history entry point)

U5 (pitch copy)      — independent, ship any time
U6 (stage labels)    — independent, ship any time
```

U5 and U6 can be shipped before or after U1–U4. Recommended order: ship U5 + U6 first (fast, low risk), then work through U1 → U4.

---

## System-Wide Impact

- **`app.py` module load time:** `_seed_db_if_empty()` runs once at startup. With 618 sessions, bulk JSON parse + SQLite insert takes < 2s locally. On Railway cold start (slower I/O), budget up to 5s. This is before the first request, not in the request path.
- **Railway ephemeral storage:** The seed approach means each deploy re-seeds from the committed JSON. If someone manually runs a pipeline analysis and saves a new session, it will disappear on the next deploy. This is acceptable for a demo.
- **`/api/trends/IJE0S/narrative` cost:** One GPT-4o call per Railway deploy instance lifetime (~$0.002–0.005 per call). Cached in-process after first call. Not called on page load — only when user navigates to the trend view.
- **No schema migration needed:** `SessionRecord` already has `overall_score` and `system_scores` fields. The new `get_health_trend()` method queries existing columns.

---

## Deferred Implementation Notes

- The trend narrative prompt text is a planning-time unknown — implementer should derive it from the existing `prompts/system_prompt_v2.txt` structure but target aggregate stats (mean scores, trend direction, date range) rather than per-session PID values
- Exact CSS for the history entry point banner should follow the existing panel/card visual language — implementer decides exact padding/color at implementation time
- If `score_vehicle_health()` returns no valid systems for a session (e.g., the CSV has no fuel trim data), the seed script should store `overall_score = None` and `system_scores = {}` — health endpoint filters these out via `AND overall_score IS NOT NULL`

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Some BMW CSV files fail ingest (format edge cases, short sessions) | Medium | Seed script catches per-file errors, logs them, continues; even 200 good sessions out of 618 is enough |
| Seed JSON file is too large for git | Low | 618 sessions × ~8 KB each = ~5 MB; well within git limits |
| Railway cold start too slow with seeding | Low | Seeding is synchronous before first request; 5s is acceptable for a demo |
| GPT-4o narrative call times out | Low | Narrative endpoint has independent error handling; rest of trend view renders without it |
| Health timeline looks flat (all sessions score 0.8–0.9) | Medium | Real concern — if BMW is consistently healthy, the chart is uninteresting; mitigated by per-system cards showing variation |
