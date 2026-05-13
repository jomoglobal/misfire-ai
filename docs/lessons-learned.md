# Lessons Learned
*MisfireAI · IAI09 Capstone · May 2026*

---

## 1. Domain Depth Makes the Demo Unassailable

The OBD2 signal was chosen over three other solid capstone ideas — auction scraping, video pipelines, hardware bundling — primarily because of firsthand automotive domain knowledge built from four years at BBG Automotive and hands-on diagnostic work. The lesson isn't that you should always pick what you already know. It's that when you're on stage and someone asks a hard question, **there is no substitute for having actually done the work.** Credentials, shop time, and real diagnostic reps make every answer credible and every design decision defensible.

---

## 2. AI Needs Operating Context to Make Real Diagnostic Decisions

A fuel trim reading doesn't mean anything without context. The same number — say, +8% long-term fuel trim — means completely different things depending on whether the engine is cold or warmed up, whether the vehicle is at idle or under load, whether both banks are showing the same reading or just one, and how long the condition has been present. **An AI agent that only sees the raw number will give a generic answer. An agent that sees the full operating picture — engine temp, run time, drive cycle state, bank symmetry — can reason the way a real technician does.**

This is why the pipeline was designed to pass not just PID values but the full diagnostic context block to the agent. The difference between a vacuum leak, a bad injector, and a failing O2 sensor can come down to whether the fuel trim anomaly is on one bank or both, and at what RPM range it appears. Operating context is not optional enrichment. It changes the diagnosis.

---

## 3. Extensive Dataset Research Was Required to Find Usable Signal

Twelve public OBD2 datasets were identified, evaluated, and documented. Of those, only three made the cut for actual use. The process involved downloading each dataset, parsing the files, inspecting column names and data types, checking for the specific PID columns that matter most (fuel trims, O2 sensors, DTCs, catalyst temp), and assessing data quality. All of this was documented in a dedicated research file — `docs/dataset-research.md` — so the evaluation rationale is on record.

The three selected datasets each covered something the others didn't:
- **carOBD** — clean fuel trim data, catalyst temp, real driving sessions, Toyota Etios
- **cephasax** — the only public dataset found with actual DTC fault codes present (11,925 rows with real codes), multi-make
- **Isay Gerard** — the only public dataset with O2 sensor waveforms and labeled driving behavior (aggressive vs. normal), 1.1 million rows, KIA Soul

No single dataset had everything. **The signal coverage map — what PIDs are present, what's missing, and why it matters — drove every inclusion and rejection decision.** Defining what the model needs before evaluating sources is the right order. Doing it the other way wastes time.

---

## 4. Real Data Exposes False Signals That Clean Specs Don't Predict

One early version of the health scoring system was calibrated against textbook specs — what the manuals say a healthy reading "should" be. When it ran against real OBD2 data, it flagged a Toyota Etios running at a perfectly normal coolant temperature as a near-failure cooling system. The spec said one thing. The actual sensor on that engine, in that vehicle, in real operating conditions, read differently.

**This is the signal-vs-noise problem in practical form.** A scoring model that generates false alarms on normal data is worse than no model at all — it trains users to ignore warnings. The fix was to inspect real dataset values first, observe the actual operating ranges vehicles produce, and calibrate thresholds from measured reality rather than specification sheets. This is an ongoing process. Every new vehicle type and every new dataset potentially reveals new calibration needs.

---

## 5. ELM327 Adapters Produce Known Artifacts That Look Like Faults

The ELM327 chip — used in most consumer Bluetooth OBD2 adapters — has known edge cases where it returns values that look like sensor readings but aren't. For example, a counter that tracks warm-up cycles since codes were cleared was stuck at 255 across every row of multiple datasets. Fuel trim readings occasionally showed extreme negative values that no real engine would produce. These aren't sensor faults. They're artifacts of how the ELM327 chip handles integer overflow and rollover at the edges of its measurement range.

**Without knowing these specific artifacts exist and what values they produce, a diagnostic system will classify them as critical faults.** Part of building a reliable signal pipeline is building in a list of known bad values per sensor and filtering them before scoring. The lesson more broadly: any data source — hardware, protocol, or software — has its own class of artifacts. Find them before they find you.

---

## 6. More Data and More Patterns Give the AI Agent Better Resources

The agent's ability to make accurate, nuanced recommendations is directly proportional to the quality and breadth of the data it's working with. A single data point is a number. A pattern across hundreds of sessions is evidence. A pattern across multiple vehicles, engine types, and operating conditions becomes something the agent can reason about with real confidence.

**This is why multi-dataset ingestion, multi-vehicle testing, and the eventual accumulation of personal session history all matter.** Each additional data source doesn't just add rows — it adds context, variation, and edge cases that sharpen the model's ability to distinguish a real developing fault from a one-time anomaly. The more the agent has seen, the better it gets at knowing what to flag and what to ignore.

---

## 7. Mode 06 Data Is the Best Signal Nobody Is Using

Standard OBD2 scanners — including most professional shop tools — read Mode 01 data and report a pass/fail for each on-board monitor. What they don't surface is Mode 06: the raw measured value plus the minimum and maximum thresholds the vehicle's own computer uses to decide pass or fail. That margin data already exists inside the ECM. It's being computed every drive cycle. Almost no one is reading it.

The significance for predictive diagnostics: a catalyst monitor at 91% of its failure threshold "passes" every scanner on the market. The vehicle hasn't set a DTC. No warning light is on. But the trend is there. **Mode 06 is how you catch a developing fault two or three oil changes before it becomes a repair.** After surveying twelve public datasets, every single one was missing Mode 06 data entirely — it's simply not collected by the tools most people use. Integrating Mode 06 is a planned future enhancement for MisfireAI, pending hardware that can reliably pull it. This remains one of the most valuable gaps to close.

---

## 8. MCP Tools Are Most Useful When They're Truly Atomic

The MisfireAI pipeline is built on four atomic MCP tools, each doing exactly one thing:
- `ingest_file` — parse a log file and return a normalized PID snapshot
- `decode_vin` — look up vehicle make/model/year/engine from a VIN via the NHTSA API
- `lookup_tsb` — retrieve recalls and complaints for a VIN and symptom
- `score_vehicle_health` — score each vehicle system on a 0–1 scale from the PID snapshot

**Keeping each tool to a single responsibility meant each one could be traced, tested, and debugged independently.** When a score came back wrong, it was immediately clear which tool produced it. When a trace appeared in Phoenix, each stage was a separate span with its own attributes. The lesson: atomicity isn't just good design theory. It's what makes a pipeline readable when something goes wrong, and demonstrable when you're showing it off.

---

## 9. Privacy Boundaries Require Real Definitions, Not Just Good Intentions

When building the compliance documentation for MisfireAI, the question came up of whether to collect environmental context like elevation and barometric pressure. The first instinct was to restrict it because it sounds like location data. On closer examination, **a single number in meters is not a route, not a destination, and not an identity.** It's a diagnostic input.

Barometric pressure drops with altitude. An engine at 5,000 feet reads lean relative to sea-level norms because there's less oxygen in the air. If the scoring model doesn't account for elevation, it will generate false alarms for anyone living or driving at altitude — Denver, Salt Lake City, Albuquerque, anywhere in the mountains. Treating elevation the same as GPS coordinates would make the diagnostic model wrong for a significant portion of users.

The broader lesson: **privacy decisions need to be grounded in what data actually reveals, not what it superficially resembles.** Elevation is diagnostic context. GPS coordinates are location tracking. They're different things, and the distinction matters for both the user experience and the compliance posture.

---

## 10. HITL Design Should Shape the Pipeline, Not Bolt Onto It at the End

The human-in-the-loop approval gate was in the rubric from day one — any repair brief generated by the agent requires owner review and approval before it's acted on. In practice, the approval flow (email delivery, Approve/Reject buttons, callback server, token-based logging) was built after the rest of the pipeline was already in place.

**The takeaway is that high-stakes output design should inform the pipeline from the start.** What format does the output need to be in to be useful in an approval email? What vehicle context does the owner need to make an informed decision? What gets logged on approval, and what gets logged on rejection? Thinking through the approval experience first would have shaped the agent's output format and the score presentation from the beginning. For Part 2, any new output type gets its stakes × reversibility analysis before the code.

---

## 11. Building a Portable, Cloneable Repo Requires Intentional Design

One of the stated goals from early in the project was that anyone should be able to pull the GitHub repo and run the pipeline without needing the original developer's machine, accounts, or local files. Getting there required deliberate decisions at every layer:
- Sample data committed to `data/sample/` so the pipeline has something to run against
- A `.env.example` file that documents every required key without exposing values
- Clear entry points documented in the README
- Dependencies managed cleanly in `requirements.txt`

Part of building toward portability also meant setting up a custom email domain for the HITL approval flow — so the approval emails come from the application itself, not a personal account. **A product that feels real in a demo needs to behave like a real product.** That means real transactional email from a real app domain, not a workaround. The process of registering and configuring a custom domain for this purpose was itself a learning experience in what it takes to stand up a deployable application vs. a local prototype.

---

## 12. Claude Code in VS Code Dramatically Accelerated the Build

One of the most significant workflow discoveries in this project was using Claude Code — the VS Code extension — not just for writing new code, but for finding and reusing prior work. When asked to locate configuration files, test datasets, and working infrastructure from previous versions of this project idea (developed in earlier capstones), Claude Code searched the local machine, found the relevant files across different project folders, pulled forward the working pieces, and integrated them into the new pipeline.

**This dramatically reduced the time spent rebuilding things that already existed.** Instead of starting from scratch on the eval harness, the Phoenix tracing setup, the OBD2 preprocessor, and the system prompt, the existing working versions were located and ported. The result was a full pipeline — including log file ingestion, health scoring, agent analysis, and Phoenix trace logging — running and tested faster than a manual rebuild would have taken by a significant margin.

The lesson: **prior work is an asset, but only if you can find it and reuse it.** Having an AI assistant that can search a local codebase, understand what it's looking at, and selectively extract useful pieces turns months of prior effort into a reusable foundation rather than buried history.

---

## 13. Architecture Diagrams Are Worth the Investment Before Coding

The Excalidraw architecture diagram for MisfireAI went through multiple iterations before landing on a version that accurately represented the four-stage pipeline, the HITL gate, and the Phoenix tracing layer. The process of building the diagram forced clarification of questions that weren't fully resolved in the design documents — specifically, how the stages hand off to each other, where Phoenix observes the pipeline, and how the HITL gate sits relative to the compound output stage.

**Diagramming is a thinking tool as much as a communication tool.** A diagram that you draw just to show someone else is a different exercise from a diagram you draw to figure out if your design actually makes sense. In this project, the architecture diagram revealed a few places where the mental model and the actual code were slightly out of sync — which is exactly what it's supposed to do.

---

*Drafted May 2026 — IAI09 Capstone, Part 1*
