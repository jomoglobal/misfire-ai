# PitLane — Capstone Brainstorm Summary
*Intelligent Automation Immersive · 9BRAINS / Divergence Academy / Helm · May 2026*

---

## Context

This document summarizes a brainstorming session conducted on Day 1 of a 6-week capstone program. The capstone theme is **Signal Harvester** — a pipeline that catches a signal, enriches it, separates signal from noise, and compounds it into action. The deliverable is a GitHub repo (clonable by a stranger) and a live demo. Graded in two parts: Part 1 MVP due May 14, Part 2 integration due June 4, Final Demo June 10.

---

## Projects Considered

### Option 1 — Auction Signal Harvester (AutoBid Intelligence)
- **Signal type:** Market Signal
- **Concept:** Scrape public salvage and collector auction sources (Copart, IAAI, Bring a Trailer) for listings and sold results. Enrich with LLM analysis. Surface underpriced units and anomalies. Output to dashboard or Google Sheet with watch-list alerts.
- **Datronex angle:** Potential B2B service for fleet managers, insurance companies, eBay resellers, and independent dealers.
- **Personal use:** Personal vehicle builds and the foundation of a potential rebuilding/flipping or parts salvage business.
- **Data sourcing:** Copart, IAAI, and Bring a Trailer are publicly visible without dealer accounts. Manheim and ADESA are dealer-only wholesale and not publicly accessible without credentials.
- **Status:** Strong idea, well-mapped pipeline. Parked in favor of PitLane based on prior work and classmate/instructor reception.

### Option 2 — OBD2 Vehicle Data Pipeline (PitLane) ✅ SELECTED
- **Signal type:** Reactive Signal (sensor anomalies, thresholds, system state)
- **Concept:** Ingest OBD2 data from vehicles, use AI to perform deeper analysis than a standard code reader, surface patterns across live sensor data, and produce actionable plain-language output.
- **Why selected:** Two prior capstone presentations on this topic. Classmates and instructor expressed genuine enthusiasm. Strong domain credibility from BBG Automotive (4 years) and active personal vehicle projects. Can talk about it 20 minutes without notes — directly satisfying Rubric Principle 1.

### Option 3 — AI Video/Media Pipeline (ReelMind)
- **Signal type:** Research/Reactive hybrid
- **Concept:** Ingest raw video and photo libraries, classify and tag content using vision model inference, select clips based on user-defined criteria, compile highlight reels.
- **Status:** Visually compelling demo. Real personal use case (hiking, car shows, travel footage). Parked for now but viable future project.

### Option 4 — OBD2 Hardware Platform (PitLane Hardware Layer)
- **Concept:** Pre-configured Bluetooth ELM327 + Raspberry Pi Zero bundle that runs the capture agent locally and pipes to cloud stack. Sell as a hardware kit via Datronex.
- **Status:** Long-term product vision. Not in scope for capstone but informs architecture decisions.

---

## PitLane — Selected Project

### The Core Value Proposition
Standard scan tools surface DTCs after the fact. PitLane's differentiator is **proactive pattern analysis across live sensor data** — correlating multiple PIDs to surface what's wrong before or beneath the code. The output isn't just a fault code. It's a plain-language interpretation of what the sensor constellation is telling you and why.

*Example:* A P2441 (secondary air injection switching valve) tells you a code. PitLane correlates short-term fuel trims, O2 sensor readings, MAF values, and engine load at cold start to explain exactly what the system is observing and what it means.

### Signal Pipeline Mapped to Rubric

| Stage | PitLane Implementation |
|-------|----------------------|
| **Catch** | OBD2 data via ELM327 adapter. Standard Mode 01 PIDs universally. Sample data in repo for clonability. |
| **Enrich** | LLM analysis on raw PID values. Cross-reference fault patterns, repair databases. Embeddings for pattern matching across sessions. |
| **Separate** | Signal-vs-noise scoring with operating context (engine temp, run time, drive cycle state). Sustained anomaly vs transient spike logic. |
| **Compound** | Plain-language session report, running vehicle health timeline, repair brief, threshold alerts mid-session. |

### Part 1 → Part 2 Progression

**Part 1 MVP (due May 14):**
- Universal OBD2 Mode 01 PIDs only (works on any 1996+ US vehicle)
- Sample data in repo — solves clonability requirement
- End-to-end pipeline: catch → enrich → separate → compound
- Human-in-the-loop approval gate before any repair recommendation is logged
- 4+ atomic MCP server tool endpoints
- Phoenix traces showing pipeline running

**Part 2 Integration (due June 4):**
- Manufacturer-specific PID layer — AI-assisted protocol analysis to identify what a specific vehicle is broadcasting beyond standard range
- Multi-agent architecture: one agent for universal analysis, one for manufacturer-specific protocol interpretation
- Eval harness: 10+ test cases across multiple vehicles (friends, family, potentially rental vehicles)
- State persistence across context windows
- Production safety audit

### Data Strategy

**For the capstone repo:**
- Sample OBD2 datasets from Kaggle, UCI ML Repository, GitHub academic research repos
- README is honest about sample data — rubric rewards this
- Multi-vehicle testing during the build window (family/friends cars) expands real data diversity

**Universal PID scope (Mode 01 — works on all 1996+ US vehicles):**
- RPM, cooldown temp, MAF, O2 sensors, fuel trims, calculated load, vehicle speed, and ~80 total parameters
- Rich enough for the entire Part 1 MVP

**Manufacturer-specific layer (Part 2):**
- Mini VCI cable + Techstream (Toyota-specific) currently operational — active learning happening now
- Boundary mapping: what's universal vs what requires manufacturer access
- This firsthand research is directly defensible in Q&A

### Human-in-the-Loop Design
High-stakes action in PitLane = a recommended repair or parts replacement. Agent surfaces finding and recommendation. Human confirms before anything is logged as a formal recommendation. Maps directly to rubric's stakes×reversibility requirement.

### The Multi-Vehicle Angle
Testing on friends/family/rental vehicles during the build:
- Real variance across makes, models, problem profiles
- Strengthens eval harness with diverse inputs
- Demonstrates the universal PID approach actually works across vehicles
- Makes the demo story more compelling

---

## Product Roadmap (Beyond Capstone)

| Phase | Description |
|-------|-------------|
| **Phase 1 — Capstone** | Software only. Sample OBD2 data in repo. Pipeline proves concept end-to-end. |
| **Phase 2 — Hardware Bundle** | Pre-configured BT ELM327 + Raspberry Pi Zero. Runs capture agent locally, pipes to cloud. Sold as Datronex kit. |
| **Phase 3 — Dyno Integration** | Planned chassis dyno becomes data collection centerpiece. PitLane is the software layer that makes dyno data actionable. |

---

## Capstone Rubric Highlights

- **Pass threshold:** 70/100 per part
- **Heaviest weights Part 1:** Signal Pipeline End-to-End (25pts), Atomic Tools & Context Design (15pts), Signal-vs-Noise Logic (15pts)
- **Heaviest weights Part 2:** Multi-Agent Architecture (18pts), Evaluation Harness (18pts), Portfolio & Demo Day (20pts)
- **Three Pillars required in both parts:** Product Management, Systems Thinking, Compliance Management
- **Key deliverables due EOD Tue May 6:** `product-brief.md`, `context.md`, `architecture.md`, `signal-decision.md`

---

## OBD2 Research Starting Prompt

Use this in a new chat to begin the technical deep dive:

> *"I want to build a foundational understanding of OBD2 from the ground up. Start with the standard itself: what SAE and ISO standards define it, what Mode 01 through Mode 10 cover, how PIDs are structured, what the difference is between generic OBD2 PIDs and manufacturer-specific PIDs, and how the physical and protocol layers work (CAN bus, ISO 9141, KWP2000, etc). I want to understand what data is universally accessible on any 1996+ US vehicle versus what requires manufacturer-specific tools or protocols. I'm building a software pipeline that ingests OBD2 data and uses AI to do deeper analysis than a standard code reader, so I want to understand both what's possible with universal access and where the ceiling is."*

---

## Key Decisions Made

- **Project selected:** Vehicle diagnostics AI pipeline (working title TBD — PitLane used informally)
- **Primary user:** Anyone who owns, operates, or has a stake in a vehicle's health — mechanic trust gap is the demo hook, not a product limitation
- **Data approach:** Sample data in repo for Part 1, real multi-vehicle data for testing. Multi-source by design.
- **Stack decision:** Ubuntu + VS Code + python-OBD library
- **Datronex angle:** Yes — long-term hardware+software product play
- **Hardware target:** Cheap ELM327 (~$10 on eBay) or ESP32 + CAN transceiver — affordable for mass adoption
- **Part 1 scope:** Universal PIDs + file ingestion, software only, sample data
- **Part 2 scope:** Manufacturer-specific protocol layer, multi-agent architecture, eval harness
- **HITL gate:** Repair brief requires owner review and approval before sending to mechanic
- **Success metric:** Non-technical user can verify or challenge a mechanic's diagnosis using pipeline output

---

## Rubric Coverage Map

### Part 1 — All Criteria Addressed

**Signal Pipeline End-to-End (25pts)**

| Stage | Implementation |
|-------|---------------|
| Catch | `ingest_file` (sample data/MHD/Techstream CSV) + `ingest_elm327` (live BT) |
| Enrich | LLM interprets raw PID values + cross-reference fault patterns via `decode_vin`, `fetch_mode06_thresholds`, `lookup_tsb` |
| Separate | Severity-tiered anomaly classification — Mode 06 thresholds as primary layer, statistical deviation as fallback |
| Compound | Persistent health dashboard + on-demand repair brief + proactive notification |

**Atomic Tools (15pts) — 8 tools defined, all single-purpose:**

| Tool | Layer | Does One Thing |
|------|-------|---------------|
| `ingest_elm327` | Catch | Reads ELM327 BT connection → raw PID data |
| `ingest_file` | Catch | Parses log file (MHD/Techstream/sample) → normalized PID data |
| `decode_vin` | Enrich | VIN → make/model/year/engine via NHTSA API |
| `fetch_mode06_thresholds` | Enrich | PID → known min/max reference values |
| `lookup_tsb` | Enrich | VIN + DTC → relevant TSBs and recalls |
| `classify_anomaly` | Separate | Reading + context → severity tier 1–4 + reasoning |
| `score_vehicle_health` | Separate | Normalized PID data → health score per system |
| `generate_repair_brief` | Compound | Flagged anomalies → plain-language output |

**Signal-vs-Noise Logic (15pts) — Severity-tiered, time-aware:**
- **Tier 1 — Immediate:** Single reading crosses critical threshold (detonation, coolant spike, oil pressure drop). Notify immediately, no pattern required.
- **Tier 2 — Pattern:** Multiple related sensors deviating together within a session. Correlate before notifying.
- **Tier 3 — Persistence:** Same reading degrading across sessions over time. Leading indicator of wear or dirty filter.
- **Tier 4 — Cliff drop:** Value normal → suddenly at limit. Points to sensor death, wiring fault, or acute component failure.

**Product Management Pillar (10pts):**
- User: Anyone with a stake in a vehicle's health
- Problem: Vehicles generate rich diagnostic data that owners can't access or interpret — leaving them dependent on mechanics with no independent verification
- MVP: Ingest OBD2 data from any source, score vehicle health, generate plain-language repair brief on demand
- Success metric: Non-technical user can verify or challenge a mechanic's diagnosis using pipeline output

**Systems Thinking Pillar (10pts):**
- Multi-source ingestion layer normalizes data from ELM327, MHD, Techstream, sample files into common schema
- Mode 06 thresholds as primary scoring layer — vehicle's own pass/fail boundaries
- Personal baseline accumulates over time per vehicle — gets smarter with more data
- Failure modes: missing Mode 06 data (fallback to statistical), hardware connection loss (fallback to file), VIN decode failure (fallback to generic thresholds)

**Compliance + Approval Flow Pillar (10pts):**
- **HITL Gate 1 (MVP):** Repair brief → owner reviews → owner approves → sent to mechanic
- **HITL Gate 2 (future):** Vehicle data → owner approves → shared with third party (insurer, fleet, dealer)
- **Governance note covers:** VIN + vehicle identity, sensor/fault code data, owner PII, third-party sharing rules
- **Hard nos:** No selling data, no sharing without explicit owner consent, no DTC clearing without confirmation
- **What gets logged:** All pipeline runs, all anomaly classifications, all HITL decisions with timestamp

### Part 2 — Integration Targets
- Multi-agent: universal PID agent + manufacturer-specific protocol agent
- Eval harness: 10+ test cases across multiple vehicles (friends/family/rentals)
- State persistence: vehicle health baseline survives context clearing
- Production safety: sandbox, permissions, audit log, rollback
- Lethal trifecta audit: VIN/PII (private data) × TSB scraping (untrusted content) × third-party sharing (exfil)

---

## OBD2 Knowledge Base
*Compiled from prior research sessions covering SAE J1979, OBD2 architecture, hardware hierarchy, and PitLane AI pipeline planning.*

### What OBD2 Is and Why It Exists
OBD2 (On-Board Diagnostics, version 2) is federally mandated on all US light-duty vehicles from 1996 onward, medium-duty from 2005, heavy-duty from 2010. Driven by EPA and CARB to standardize emissions monitoring. The key constraint: **OBD2 was designed for emissions-related systems only.** Everything beyond that boundary is voluntary, proprietary, and hidden behind manufacturer-specific protocols.

### Standards Architecture

| Standard | What It Governs |
|---|---|
| **SAE J1979** | Core US diagnostic services — defines Modes 01–0A, PID structure, mandatory data |
| **ISO 15031-5** | International equivalent of SAE J1979 |
| **SAE J1962** | Physical 16-pin OBD2 connector |
| **ISO 15765-4** | OBD2 messages over CAN bus |
| **ISO 15765-2** | ISO-TP transport layer — CAN message segmentation/reassembly |
| **ISO 14230 (KWP2000)** | Older protocol layer pre-CAN |
| **ISO 9141-2** | Older protocol, common European/Asian pre-CAN vehicles |
| **SAE J1850** | Older US protocol (VPW=GM, PWM=Ford) |
| **SAE J2534** | Pass-Thru software API — standardizes PC↔hardware adapter communication |
| **SAE J1939** | Heavy-duty variant (trucks/buses) — uses PGNs instead of PIDs |
| **ISO 14229 (UDS)** | Unified Diagnostic Services — foundation for manufacturer-specific Mode 22 |
| **SAE J1979-2** | OBDonUDS successor standard (2021) — mandatory for US vehicles ~2027 |

### Physical Protocols

| Protocol | Era | Notes |
|---|---|---|
| **CAN** (ISO 15765-4) | 2003+ (mandatory 2008+) | Universal on all modern vehicles. Pins 6, 14. |
| **ISO 9141-2** | ~1996–2004 | European/Asian vehicles. Pins 7, 15. |
| **KWP2000** (ISO 14230-4) | ~2000–2007 | Overlaps 9141 physically. Pins 7, 15. |
| **J1850 VPW** | ~1996–2007 | GM-specific. Pin 2. |
| **J1850 PWM** | ~1996–2007 | Ford-specific. Pins 2, 10. |

> **Practical rule:** Any 2008+ vehicle uses CAN exclusively.

**Key CAN addresses:**
- `0x7DF` — broadcast address (query all ECUs)
- `0x7E0` — ECM physical address
- `0x7E8` — ECM response address
- `0x7E1` — TCM physical address

### The Ten Diagnostic Modes

| Mode | Name | Key Notes |
|---|---|---|
| **01** | Current Powertrain Data (Live) | Real-time PIDs. Query PID 0x00 first for availability cascade. |
| **02** | Freeze Frame | Snapshot of Mode 01 at moment DTC was set. Always pull alongside DTCs. |
| **03** | Stored DTCs | Confirmed fault codes that triggered MIL. P/C/B/U prefix. |
| **04** | Clear DTCs | **Irreversible.** Treat as privileged operation. |
| **05** | O2 Sensor Monitor Results | Not used on CAN vehicles — moved to Mode 06. |
| **06** | On-Board Monitor Test Results | **Highest-leverage mode for AI diagnostics.** Raw measured values + min/max thresholds. |
| **07** | Pending DTCs | Single-cycle faults not yet confirmed. Always pull alongside Mode 03. |
| **08** | Bidirectional Control | Rarely standardized — most implementations are proprietary. |
| **09** | Vehicle Information | VIN (PID 0x02), Calibration ID, CVN, ECU name. |
| **0A** | Permanent DTCs | Cannot be cleared with Mode 04. Self-clear only after monitor completion. 2010+ vehicles. |

**Mode 01 Mandatory PIDs (every compliant vehicle):**
`0x01` monitor status, `0x03` fuel system status, `0x04` engine load, `0x05` coolant temp, `0x0B` intake manifold pressure, `0x0C` RPM, `0x0D` vehicle speed, `0x0F` intake air temp, `0x11` throttle position, `0x1C` OBD conformance.

**Mode 06 — Why It Matters for PitLane:**
Standard tools report only pass/fail. Mode 06 gives the raw measured value plus min/max thresholds. The margin between measured and threshold is a continuous health score the vehicle is already computing. A catalyst at 0.92 with a minimum of 0.90 is near-failure. A catalyst at 0.98 is healthy. Both "pass" to a standard reader. PitLane captures this gap as a predictive signal — weeks before a DTC is ever set.

Health score formula: `(measured - min) / (max - min)` → 0–1 score per monitor.

### PID Structure

**Request frame (CAN):**
```
Byte 0: Length
Byte 1: Mode (e.g., 0x01)
Byte 2: PID  (e.g., 0x0C for RPM)
```

**Response frame:**
```
Byte 0: Length
Byte 1: Mode + 0x40 (e.g., 0x41)
Byte 2: PID echoed
Byte 3+: Data bytes (A, B, C, D)
```

**Decode examples:**
- RPM: `((A × 256) + B) / 4`
- Fuel trim: `(A / 1.28) − 100` → ±100% range
- Coolant temp: `A − 40` → °C

**PID Availability Cascade:** Never assume a PID is supported. Query PID `0x00` → 4-byte bitmask for PIDs 0x01–0x1F. If bit for `0x20` is set, query `0x20` for next range. Continue through `0x40`, `0x60`, `0x80`, `0xA0`, `0xC0`. This cascade is independent per mode.

### Generic vs. Manufacturer-Specific PIDs

**Generic (SAE-defined):** Standardized, identical across all vehicles. ~15–20 truly mandatory parameters, ~60 commonly supported. Lower PID ranges.

**Manufacturer-specific:** Above certain PID ranges (typically `0x0100+` in Mode 01) manufacturers define their own PIDs with no obligation to document them. **Mode 22 (UDS ReadDataByIdentifier)** is the key gateway using 2-byte DIDs. Data behind this wall includes: individual cylinder misfire counts, injector pulse widths, transmission clutch pressures, individual wheel brake pressures, steering angle, EV battery cell voltages, ADAS sensor data, knock sensor raw values, actual engaged gear.

### Hardware Hierarchy

```
Zurich BT1 / ELM327:   Phone ←[BT]→ [ELM327 chip] ←[copper]→ OBD2 port ←→ CAN bus
ESP32 + CAN transceiver: Code ←[SPI]→ [CAN chip]   ←[copper]→ OBD2 port ←→ CAN bus
J2534 device:            PC   ←[USB]→ [J2534 hw]   ←[copper]→ OBD2 port ←→ CAN bus
```

| Feature | ELM327 | J2534 |
|---|---|---|
| Connection | Bluetooth/WiFi/USB | USB |
| Access level | Interpreted (AT commands) | Raw CAN frames |
| Cost | $10–$50 | $100–$500+ |
| Use case | Consumer apps, learning | Professional tools, ECU reprogramming |

**Zurich BT1 (Harbor Freight ~$50):** ELM327-based. Works with Repair2Sol and python-OBD library. Can query Modes 01–09, read/clear DTCs, display live data, read VIN. Cannot access Mode 22/UDS, receive raw CAN traffic, or do high-frequency capture.

**Mini VCI cable + Toyota Techstream:** Currently operational. Toyota-proprietary protocol layer exposing data far beyond generic OBD2. Serves as ground truth for understanding the universal vs. manufacturer-specific boundary — directly relevant to PitLane Part 2.

### The VIN as Rosetta Stone
Decode every VIN via NHTSA free API to get make, model, year, engine family, assembly plant. Enables vehicle-specific PID decoding, engine-family anomaly baselines, and TSB/recall flagging relevant to the VIN.

### Free Access to SAE J1979
- **law.resource.org:** 2002 edition free as legally binding document (incorporated into federal law): `https://law.resource.org/pub/us/cfr/ibr/005/sae.j1979.2002.pdf`
- **Wikipedia OBD-II PIDs:** Complete PID table with every formula — what working developers actually use: `https://en.wikipedia.org/wiki/OBD-II_PIDs`
- **Interlibrary Loan:** Request via DeVry library — takes a few days, works reliably.

### Quick Reference Numbers

| Item | Value |
|---|---|
| OBD2 mandatory US light-duty from | 1996 |
| OBD2 connector standard | SAE J1962 (16-pin) |
| CAN broadcast address | 0x7DF |
| ECM physical address | 0x7E0 |
| ECM response address | 0x7E8 |
| Standard CAN speed | 500 kbps (11-bit) or 250 kbps (29-bit) |
| PID availability query | Mode 01 PID 0x00 (cascade through 0x20, 0x40…) |
| RPM formula | ((A×256)+B)/4 |
| Fuel trim formula | (A/1.28)−100 |
| Mode for pending DTCs | 07 |
| Mode for permanent DTCs | 0A |
| Mode for raw monitor test values | 06 |

---

## Side Project — Claude Usage Monitor

### Overview
A Windows system tray application that displays Claude Pro 5-hour utilization as a color-coded number near the clock. No browser required. Built to maximize Claude Code session awareness and avoid unexpected resets.

### Current Status
- Working version exists and in active use
- Known bug: counter resets incorrectly after extended idle periods (stepping away for a long time)
- Actively being debugged

### Purpose
Claude Pro operates on a 5-hour usage window. Without visibility into where you are in that window, it's easy to lose context at a critical moment or waste time during a reset period. This tool surfaces that usage as a persistent, glanceable indicator in the system tray — solving a real workflow problem for anyone doing intensive Claude Code sessions.

### Potential
- Personal productivity tool → could become a Datronex utility offering
- Packaged and distributed to other developers doing heavy Claude Code work
- Could expand to track multiple Anthropic API metrics beyond just the usage window

### Known Issues to Resolve
- Reset detection after long idle: the counter behavior when the session expires vs. when the user is simply inactive needs to be distinguished
- Investigating whether the issue is a polling interval problem, a state persistence problem, or an API response change after idle timeout

---

*Last updated: May 5, 2026 — Day 1 brainstorm session*