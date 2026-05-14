# MisfireAI — Capstone Part 1 Slide Brief
**Course:** Intelligent Automation Immersive · Module 09 – Signal Harvester
**Format:** 10 slides · 10 minutes · Live demo
**Style:** Clean light theme — white background, professional typography
**Key message:** A fully working AI diagnostic pipeline that ingests OBD2 data from any vehicle, reasons over it autonomously, and delivers actionable repair insights to the owner — with a human approval gate before any action is taken.

---

## SLIDE 1 — Title
**Title:** MisfireAI
**Subtitle:** An Autonomous OBD2 Diagnostic Agent
**Byline:** Intelligent Automation Immersive · Module 09 · Signal Harvester · May 2026
**Visual suggestion:** Full-bleed hero — dark engine bay photo or abstract circuit/car graphic, with the MisfireAI name and a single tagline overlaid:
> *"From raw sensor data to repair decision — fully autonomous, human-approved."*

---

## SLIDE 2 — The Problem
**Headline:** Your car knows it's sick before you do
**Body points:**
- Modern vehicles generate thousands of sensor readings per drive — nearly all of it is ignored
- Standard OBD2 scanners only surface fault codes *after* a failure has already occurred
- Mechanics charge $150–200 just to read codes that any $30 dongle can pull
- Fuel trim drift, knock retard accumulation, catalyst degradation — all predictable weeks in advance with the right analysis
- No consumer product connects raw OBD2 data to AI reasoning and delivers plain-language diagnostics to the owner

**Visual suggestion:** Split: left side shows a generic OBD2 scanner displaying "No codes found" — right side shows a vehicle with multiple sub-threshold degrading systems highlighted

---

## SLIDE 3 — The Solution: MisfireAI
**Headline:** A four-stage autonomous agent pipeline
**Body:** MisfireAI is an AI agent that plugs into any vehicle's OBD2 port (or ingests existing log files), runs a full diagnostic pipeline, and delivers a plain-language repair brief to the owner — who approves or rejects it before any action is taken.

**Four pipeline stages (use a horizontal flow diagram):**
1. **CATCH** — Ingest from any source: ELM327 Bluetooth, MHD datalogger, CarScanner, Techstream. Normalize all data to a canonical 56-signal schema across 10 signal families.
2. **ENRICH** — Decode VIN via NHTSA API, look up TSBs and recalls, query historical session baseline via RAG (ChromaDB vector store), orchestrated via n8n.
3. **SEPARATE** — Classify anomalies at 4 severity tiers. Score each vehicle system (fueling, ignition, thermal, catalyst, boost, etc.) 0–1 using three methods: Mode 06 margin scoring, fuel trim trending across sessions, statistical baseline deviation.
4. **COMPOUND** — Generate plain-language AI assessment. Assemble repair brief. Trigger HITL approval gate.

**Visual suggestion:** Four colored boxes in a horizontal pipeline: CATCH (blue) → ENRICH (green) → SEPARATE (orange) → COMPOUND (purple), with a red HITL gate at the end.

---

## SLIDE 4 — Agent Architecture & Tool Design
**Headline:** Six atomic MCP tools — one agent, zero hardcoded logic
**Body:** The agent is built on the Model Context Protocol (MCP). Each pipeline stage is a discrete, observable tool call. The agent decides when and how to invoke them based on available data.

**Tool table (two columns: Tool Name | What it does):**
| Tool | Purpose |
|---|---|
| `ingest_file` | Parse any CSV log → normalized PID snapshot |
| `decode_vin` | VIN → vehicle metadata via NHTSA API |
| `lookup_tsb` | VIN → TSBs, recalls, complaints |
| `score_vehicle_health` | Normalized snapshot → per-system 0–1 scores |
| `ingest_batch` | Batch ingest entire folder of logs → session store |
| `query_trends` | Longitudinal PID trend across all sessions for a vehicle |

**Key design principle:** Every tool call is traceable. No tool has side effects outside its declared scope. The agent cannot write to the vehicle ECU — read-only by design.

**Visual suggestion:** Icon-grid of the 6 tools with a small description under each, connected by thin arrows showing the call sequence.

---

## SLIDE 5 — Data Pipeline & Multi-Source Ingestion
**Headline:** One schema. Any vehicle. Any logger.
**Body:**
- **5 data sources supported:** MHD (BMW performance datalogger), CarScanner, CarOBD, CephaSAX (multi-make Brazil fleet), iSay Gerard (KIA Soul, Spanish headers)
- **56 canonical signals** across 10 families: fueling, ignition, thermal, boost, catalyst, fuel_supply, exhaust, composition, drivetrain, meta
- **Auto-detection:** Source identified from column headers — no manual config required
- **Unit normalization:** All temperatures → °C, speeds → km/h, MAP → kPa on ingest
- **Delimiter & encoding handling:** UTF-8 BOM, semicolon vs. comma, European decimal commas, trailing unit suffixes (e.g. `82C`, `79,20%`) — all handled transparently

**Scale already ingested:**
| Vehicle | Source | Sessions |
|---|---|---|
| 2009 BMW 335i (personal) | MHD datalogger | 394 |
| Toyota Etios fleet | CarOBD | 142 |
| Multi-make Brazil fleet | CephaSAX | 7 |
| KIA Soul | iSay Gerard | 4 |
| **Total** | | **548 sessions** |

**Visual suggestion:** Bar chart of sessions per vehicle, with a small "source logo / label" under each bar.

---

## SLIDE 6 — Predictive Health Scoring
**Headline:** Three scoring methods — works with any hardware
**Body:** MisfireAI doesn't wait for a DTC. It computes a 0–1 health score per system using whichever method the available data supports:

**Method 1 — Mode 06 Margin Scoring** *(best, hardware-dependent)*
> Uses the vehicle's own internal thresholds. A catalyst at 91% of its minimum passes a standard scan — MisfireAI flags it.
> `margin = (measured − min) / (max − min)`

**Method 2 — Fuel Trim Trending** *(core method, any hardware)*
> LTFT creeping from +3% → +7% → +11% across 20 sessions is a leading indicator weeks before a DTC fires.
> `trend_score = 1 − (current_ltft / saturation_limit)`

**Method 3 — Statistical Baseline Deviation** *(fallback, first-session capable)*
> Compares current session to personal vehicle baseline. Coolant 8°C cooler than 30-session average at matching RPM → thermostat degrading.

**4 anomaly severity tiers:**
- **Tier 1 — Immediate:** Single reading crosses critical threshold
- **Tier 2 — Pattern:** 2+ related sensors deviating together
- **Tier 3 — Persistence:** Same reading degrading across multiple sessions
- **Tier 4 — Cliff Drop:** Normal → limit in a single session

**Visual suggestion:** Three stacked method descriptions with a small score dial graphic (0–1) on the right.

---

## SLIDE 7 — HITL: Human-in-the-Loop
**Headline:** High stakes = human approval. Always.
**Body:** MisfireAI classifies every action by stakes and reversibility. Only irreversible, high-stakes outputs are gated.

**Approval matrix table:**
| Action | Stakes | Reversible | Gate |
|---|---|---|---|
| Session report generated | Low | — | Auto-logged |
| Anomaly classified | Medium | Yes | Auto-logged with reasoning |
| Health score computed | Medium | Yes | Auto-logged |
| **Repair brief** | **High** | **No** | **Owner approval required** |
| DTC clear (Mode 04) | High | No | **Permanently blocked** |
| ECU write | High | No | **Out of scope** |

**Approval flow:**
1. Agent generates repair brief
2. SendGrid sends dark-theme HTML email from `misfire@datronex.net`
3. Email shows: vehicle, urgency badge, per-system health scores, active DTCs, AI assessment
4. Owner clicks **Approve** or **Reject**
5. FastAPI callback server captures decision + UTC timestamp
6. Decision logged to Phoenix trace — immutable

**Channels:** Email ✅ Live · Telegram 🔜 Planned · Slack 🔜 Future

**Visual suggestion:** Show a screenshot of the actual HITL approval email with Approve/Reject buttons visible.

---

## SLIDE 8 — Observability & Compliance
**Headline:** Every decision is logged. Nothing is hidden.
**Body:**

**Tracing:** Phoenix/Arize OTel traces every tool call — stage, inputs, outputs, duration, warnings. Traces are immutable once written.

**What gets logged:**
- `ingest_file` — source format, row count, PID count, warnings
- `decode_vin` — VIN (hashed), decoded vehicle, NHTSA response
- `score_vehicle_health` — per-system scores, method used, data gaps
- `classify_anomaly` — tier, PIDs flagged, reasoning, confidence
- `generate_repair_brief` — brief content, delivery channel, owner decision, timestamp
- HITL gate — approver, timestamp, brief hash

**Hard compliance rules (never breakable):**
- No Mode 04 (DTC clear) — ever
- No ECU writes — read-only from the vehicle
- No external data sharing without a logged approval event
- VIN always hashed before leaving the device
- No GPS, no owner identity, no financial data collected

**Visual suggestion:** Small OTel trace diagram showing spans for each tool call with timestamps.

---

## SLIDE 9 — Live Demo
**Headline:** Working system — running right now
**Body (talking points for the demo, not bullet points on slide):**

*What to show:*
1. Open `http://[laptop-ip]:8000` on phone + laptop simultaneously
2. Select **bmw-335i-IJE0S** from the vehicle library dropdown (394 real sessions, 2023–2026)
3. Pick a recent log file — click **Run Analysis**
4. Walk through the four pipeline panels as they stream in:
   - **CATCH:** source detected as MHD, signals captured (boost, AFR, knock retard, STFT)
   - **SEPARATE:** per-system health scores, anomaly tier classification
   - **COMPOUND:** AI assessment in plain language, urgency badge
   - **VEHICLE HISTORY:** sparkline cards showing 200 sessions of STFT, BOOST, KNOCK_RETARD trends over time
5. Switch to **TRENDS tab** — plot KNOCK_RETARD across all BMW sessions (2024–2025)
6. If time: show HITL email flow with Approve/Reject buttons

**Slide visual:** Single full-width screenshot of the live UI showing the pipeline panels filled in — CATCH, SEPARATE, COMPOUND all visible.

**Backup:** Screenshots of each panel already saved; can walk through statically if live demo has issues.

---

## SLIDE 10 — What's Next (Part 2)
**Headline:** Part 1 is a working foundation. Part 2 is the product.
**Body:**

**Part 1 — Complete ✅**
- Full 4-stage diagnostic pipeline
- 6 MCP tools, MCP server, agent loop
- 548 sessions ingested, 5 vehicles
- HITL email approval gate (live)
- Browser UI with library picker, trends tab, vehicle history sparklines
- Phoenix/Arize OTel observability
- Mobile-accessible (local network)

**Part 2 — Roadmap**
- Live ELM327 Bluetooth connection (real-time streaming, not file import)
- Telegram HITL approval channel
- Cloud deployment (`app.datronex.net`) — Railway or Fly.io
- ESP32 + CAN transceiver DIY hardware build (~$20, replicable by anyone)
- Comparative fleet benchmarks: "Your Tundra's LTFT is +4% — median for 1GR-FE at this mileage is +1.5%"
- Mode 06 margin scoring via Dragy / Zurich BT1 hardware testing
- Mobile app wrapper (PWA)

**Closing line:**
> *MisfireAI isn't a demo. It's ingesting real data from a real car right now. Part 2 turns it into something anyone can use.*

**Visual suggestion:** Two-column split: left = "Done" checklist in green, right = "Next" roadmap in blue.

---

## DESIGN NOTES FOR CLAUDE.AI PPTX SKILL

**Color palette (light professional theme):**
- Background: white (`#FFFFFF`)
- Primary accent: `#1a56db` (blue — use for headings, key callouts)
- Secondary accent: `#16a34a` (green — "done" items, healthy scores)
- Warning: `#d97706` (amber — medium severity)
- Critical: `#dc2626` (red — HITL gate, blocked actions)
- Text: `#111827` (near-black)
- Subtext / labels: `#6b7280` (gray)
- Table headers / section labels: `#e5e7eb` background with `#374151` text

**Typography:**
- Headings: Bold, large (36–44pt on title slide, 28–32pt on content slides)
- Body: 16–18pt, regular weight, generous line spacing
- Table text: 13–14pt
- Code / tool names: monospace, slightly smaller, light gray background pill

**Slide structure:**
- Each slide: one strong headline (the point), supporting content below
- No more than 5–6 bullets per slide — prefer tables and diagrams over long lists
- Slide 3 and Slide 6 should have visual diagrams (pipeline flow, scoring methods)
- Slide 7 should show the actual HITL email screenshot if possible
- Slide 9 (demo) should be mostly visual — large screenshot, minimal text

**Tone:** Professional but direct. This is a working system, not a concept. Every claim on the slides is demonstrated by live running code.
