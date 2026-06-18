# MisfireAI Demo — Consumer UX Reframe

**Created:** 2026-06-12
**Status:** Ready for planning

---

## Problem Frame

The MisfireAI demo at demo.datronex.net runs a live 4-stage AI diagnostic pipeline, but presents it with academic vocabulary inherited from the IAI09 divergence course lab (CATCH, ENRICH, SEPARATE, COMPOUND). The surrounding copy reinforces the student-project impression: the browser tab says "OBD2 Diagnostic Pipeline," a badge reads "OBD2 DEMO," and a form label exposes "HITL approval."

The result is three simultaneous impression gaps:
1. **Credibility** — looks like a coursework submission, not a commercial product
2. **Clarity** — a first-time visitor doesn't know what problem is being solved or for whom
3. **Personal relevance** — the output feels like a data pipeline trace, not a health report about *their* car

---

## Target Audiences

| Priority | Audience | What they need from the demo |
|---|---|---|
| Primary | Investors / accelerator judges | A product story they can immediately pitch back to others |
| Primary | Everyday car owners | Plain-language understanding of their car's health — no wrenching required |
| Secondary | Fleet operators | Confidence that long-term data logging produces actionable signal |

**North star:** every driver should have a long-term AI datalogger that teaches them about their car.

---

## Actors

- **A1 — Car owner / demo visitor:** Lands on the demo page, has no diagnostic training, wants to understand their car's health.
- **A2 — Investor / judge:** Evaluates the product story and technical credibility. Needs to grasp the value proposition in under 60 seconds.
- **A3 — Fleet operator:** Has OBD2 loggers installed, wants to see whether long-term data produces useful signal.

---

## Success Criteria

1. A first-time visitor can describe what MisfireAI does in one sentence without reading any documentation.
2. An investor watching the demo describes it as a product, not a prototype.
3. The results page reads like a doctor's visit — verdict first, explanation second, supporting data third.
4. No internal vocabulary (CATCH, ENRICH, SEPARATE, COMPOUND, HITL, OBD2 Pipeline, signal ingestion) appears anywhere in the visible UI.
5. Technical data (raw PID values) is accessible but not front-and-center — collapsed by default under "Technical Details."
6. The loading experience conveys that something meaningful is happening, without exposing pipeline internals.

---

## Scope Boundaries

### In scope
- Loading state: replace stage-by-stage panel rendering with animated rotating status messages
- Results layout: restructure into a unified "Vehicle Health Report" — verdict at top, AI narrative second, system grades third, raw signals collapsed by default
- All visible copy: stage labels, panel titles, browser tab title, badge text, sidebar hints, form labels
- Internal SSE event names: **out of scope** — rename only the visible UI layer; backend wire protocol stays as-is

### Out of scope
- Pitch copy above the form / product tagline (deferred — can be added separately as a small follow-up)
- Backend pipeline changes — no changes to what data is produced, only how it is displayed
- Mobile layout or responsive redesign
- Adding new data sources or signals

---

## Key Flows

### F1 — Demo visitor runs analysis
1. Visitor lands on demo.datronex.net
2. VIN is pre-filled; Run Analysis is enabled
3. Visitor clicks Run Analysis
4. Loading state appears with rotating consumer-friendly status messages cycling every ~3 seconds
5. When all pipeline stages complete, the full Vehicle Health Report renders at once
6. Report shows: urgency verdict at top → AI narrative → system health grades → "Show Technical Details" toggle

### F2 — Investor reviews the report
1. Investor runs the analysis (same as F1)
2. Urgency verdict and overall health score are immediately visible above the fold
3. AI narrative reads like a mechanic's summary — plain language, specific to the vehicle
4. System grades (Fueling, Cooling, Ignition, Catalyst) give a structured overview
5. "Technical Details" section is available but collapsed — shows raw PID table on expand
6. No internal labels, acronyms, or pipeline vocabulary visible anywhere

---

## Requirements

### Loading experience
- **R1:** Replace the 4-step stage progress dots with a single animated loading state
- **R2:** Status messages rotate through consumer-friendly phrases during the wait (e.g., "Reading your data...", "Looking up your vehicle...", "Scoring your systems...", "Writing your report...")
- **R3:** Messages cycle every ~3 seconds; spinner or subtle animation accompanies them
- **R4:** No stage names (CATCH/ENRICH/SEPARATE/COMPOUND) appear during loading

### Results layout — report card
- **R5:** Results render as a single unified panel, not four sequential panels
- **R6:** Report header shows the vehicle name (e.g., "2009 BMW 335d") prominently
- **R7:** Urgency verdict (NORMAL / LOW / MEDIUM / HIGH / CRITICAL) appears at the top with a clear color indicator — green for healthy, amber for watch, red for urgent
- **R8:** Overall health score (percentage) appears alongside the urgency verdict
- **R9:** AI narrative (COMPOUND output) appears as the primary body text — plain language, no markdown bolding exposed to users
- **R10:** System health grades (Fueling, Cooling, Ignition, Catalyst) appear below the narrative as a clean grid of cards
- **R11:** Raw PID data is collapsed by default under a "Technical Details" disclosure element
- **R12:** "Technical Details" expands to show the PID table (signal name, mean, unit) on user interaction
- **R13:** Recall and complaint information (from ENRICH) integrates into the report, not a separate panel — e.g., a "Known Issues" card beneath system grades if recalls > 0

### Copy — all visible text
- **R14:** Browser tab title: "MisfireAI — Vehicle Health Report" (or similar; no "OBD2 Diagnostic Pipeline")
- **R15:** Demo badge: remove "OBD2 DEMO" or replace with "Live Demo"
- **R16:** Email form label: remove "HITL" — replace with "Email (optional — get a copy of your report)"
- **R17:** Sidebar drop hint: remove app names (MHD, CarScanner, etc.) or replace with "Upload your OBD2 data file"
- **R18:** No internal acronyms (CATCH, ENRICH, SEPARATE, COMPOUND, HITL, PID as a standalone label) appear in any visible UI element
- **R19:** System grade cards use plain names — "Fuel System" not "fueling", "Engine Cooling" not "cooling", "Ignition" is acceptable, "Catalytic Converter" not "catalyst"

### Acceptance examples

**AE1 — First impression (A1/A2):** A visitor who has never heard of MisfireAI lands on the demo page. Within 10 seconds — before clicking Run Analysis — they can answer: "What does this do?" The answer should be: "It analyzes my car's data and tells me how healthy it is."

**AE2 — Loading (A1):** Visitor clicks Run Analysis. They see a spinner and the message "Reading your data..." which transitions to "Looking up your vehicle..." etc. They do not see any of: CATCH, ENRICH, SEPARATE, COMPOUND, "Signal Ingestion", or a stage progress bar.

**AE3 — Report top (A2):** An investor sees the results. The first visible element is either a green "All Clear" or a red/amber urgency indicator with the vehicle name. They do not need to scroll to understand the verdict.

**AE4 — Plain language (A1):** A car owner reads the report. They understand every word without Googling any term. "LTFT_B1" does not appear in the main body of the report — it is inside "Technical Details" if they choose to expand it.

**AE5 — Technical depth (A3):** A fleet operator or technical reviewer clicks "Technical Details" and sees the full PID table with signal names, mean values, units, and families. The depth is there; it just isn't front-and-center.

---

## Assumptions

- Internal SSE wire protocol (`stage: "catch"`, `"enrich"`, etc.) will not be renamed — only the UI rendering layer changes
- The existing pipeline output structure is unchanged — all four stages produce the same data as today
- Demo mode (VIN pre-filled, no file upload) remains; this reframe is demo-layer only
- The AI narrative (GPT-4o output) already reads in plain language — no prompt changes needed
- The "doctor's visit" layering (verdict → narrative → grades → data) can be achieved by reordering the existing rendered output, not rebuilding the pipeline

---

## Open Questions

- What should the top-level report be called? "Vehicle Health Report" is the working name — confirm or suggest an alternative at planning time.
- Should the urgency label use the current tier words (NORMAL/LOW/MEDIUM/HIGH/CRITICAL) or consumer equivalents ("All Clear" / "Watch" / "See a Mechanic")?
