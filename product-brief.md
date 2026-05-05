# Product Brief
*OBD2 AI Diagnostic Pipeline · Capstone Part 1 · May 2026*

---

## User

Anyone who owns, operates, or has a stake in a vehicle's health.

This includes everyday drivers, DIY mechanics, automotive enthusiasts, people managing a household fleet, and anyone who wants to understand what their car is actually telling them — not just what a scan tool reports after the fact.

The entry point that makes this tangible: a vehicle generates rich diagnostic data every time it runs. Most owners never see it. When they do interact with it — usually at a shop — they have no independent way to understand or verify what they're being told. This pipeline changes that. It puts the data in plain language, in the owner's hands, before any decision is made.

---

## Problem

Standard scan tools surface fault codes after a problem is already confirmed. They answer "what broke" — not "what's degrading," "what pattern is forming," or "what does this combination of readings actually mean."

The result: owners are structurally dependent on whoever holds the scanner. They can't independently interpret the data their own vehicle is producing.

PID data is rich. Coolant temp, fuel trims, O2 sensor readings, MAF values, engine load, Mode 06 monitor margins — these tell a layered story. Today, that story goes unread for most vehicle owners.

---

## MVP

Ingest OBD2 data from any supported source → score vehicle health across systems → generate a plain-language analysis on demand.

**Supported input sources (Part 1):**
- ELM327 adapter (Bluetooth live connection)
- Log file ingestion: Car Scanner app, MHD, Techstream, ESP32 CAN logger, sample data

**Pipeline stages:**
1. **Catch** — normalize data from any source into a common schema
2. **Enrich** — LLM interprets PID values; VIN decoded via NHTSA API; TSB/recall lookup; historical session comparison via RAG
3. **Separate** — 4-tier severity classification; Mode 06 margin scoring; sustained anomaly vs. transient spike logic
4. **Compound** — plain-language session report; vehicle health score per system; repair brief (HITL-gated)

**Human-in-the-loop gate:** The pipeline surfaces findings and a recommended repair brief. The owner reviews and approves before anything is logged as a formal recommendation or shared externally. High-stakes action requires human confirmation.

**Sample data in repo** — pipeline is fully runnable without hardware.

---

## Success Metric

A non-technical vehicle owner can read the pipeline's output and arrive at an informed, independent position on their vehicle's health — without needing a mechanic to interpret the data for them.

Secondary: the pipeline catches a real anomaly (degraded Mode 06 monitor margin, developing fuel trim pattern, or correlated multi-sensor deviation) that a standard code reader would not have flagged.
