# MisfireAI — Product Strategy

*Last updated: 2026-06-12*

---

## What we're building

A long-term vehicle intelligence system. Every drive a car owner logs becomes part of a growing history. The AI analyzes that history to surface patterns, drift, and anomalies that are invisible in any single session — the slow fuel trim degradation building over months, the knock retard that gets worse every summer, the cooling system that takes longer to warm up than it used to.

**The core bet:** most car problems don't appear suddenly. They develop slowly, below the threshold of what a driver notices in a single drive. A long-term data layer catches them before they become failures.

---

## The product has two layers

**Layer 1 — Instant diagnosis (single session)**
Upload one OBD2 log, get a plain-language health report in seconds. This is the entry point: fast, demonstrable, works with any car that has OBD2.

**Layer 2 — Longitudinal intelligence (multi-session history)**
Accumulate sessions over time. The system builds a vehicle health timeline, detects drift and step-changes, and generates AI narratives about what's changed and why. This is the real differentiator — no code reader does this.

The demo should demonstrate both. Layer 1 is the hook. Layer 2 is the "wait, this is different" reveal.

---

## Hardware is part of the product

At minimum, MisfireAI is a hardware + software product. The logger device is the entry point for continuous data collection. The AI analysis is the ongoing value. The exact device (MHD Orange Dongle, Dragy, future ESP32-based unit) is TBD, but the architecture already supports multiple logger formats.

---

## Who the demo is for right now

**Primary:** Developers, builders, and technical evaluators — people who will ask "is this real?" before they ask anything else. They want to see that the AI pipeline works on real data, that the analysis is legitimate, and that the architecture is serious.

**Secondary:** Investors and accelerator judges who need to understand the product story quickly, without needing to be mechanics.

**Both audiences will encounter the demo either in a direct pitch context (with explanation) or cold (no intro).** The demo must work in both modes.

---

## What the demo must prove in 60 seconds

1. **This is real data** — 394 sessions from a real BMW 335i, spanning 3 years (2023–2026)
2. **The analysis actually works** — four-stage AI pipeline runs live; results are specific, not generic
3. **This is a product, not a coursework project** — the pipeline architecture is sound, the MCP tools are real, the system is designed to scale

---

## What the demo does NOT need to prove right now

- Consumer UX polish (nice-to-have; not the validator's primary concern)
- Monetization model (undecided; not relevant to technical validation)
- Multi-vehicle support (demonstrated with BMW; architecture supports more)

---

## Near-term priorities

1. **Show longitudinal data in the demo** — seed the Railway demo with the 394 BMW sessions so visitors see the trend history, not just a single-session report
2. **Make the pipeline legible** — the CATCH/ENRICH/SEPARATE/COMPOUND stages should be explained (what each does, why it matters), not hidden. A developer wants to understand the system.
3. **One-sentence pitch above the fold** — a cold visitor needs to know what this is before they click anything

## Later (after technical validation)

- Consumer UX reframe (see `docs/brainstorms/2026-06-12-consumer-ux-reframe-requirements.md`)
- Hardware product definition (logger device + software bundle)
- Monetization model (subscription, B2B license, or hardware margin — TBD based on who wants it)
- Mobile experience
