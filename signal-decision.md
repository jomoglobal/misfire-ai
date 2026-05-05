# Signal Decision
*OBD2 AI Diagnostic Pipeline · Capstone Part 1 · May 2026*

---

## Signal Type

**Reactive Signal** — sensor anomalies, threshold breaches, system state changes.

The vehicle's OBD2 system continuously produces a stream of parametric data (PIDs) across dozens of systems. This pipeline treats that stream as a reactive signal: something to monitor, score, and act on — not just store.

---

## Why This Signal

1. **Domain depth.** Four years of hands-on automotive work means the signal is well-understood at the source — what the readings mean, what patterns precede failures, where standard tools fall short. This isn't a signal chosen for convenience; it's a domain with genuine expertise behind it.

2. **Rich, continuous, and underutilized.** Every 1996+ US vehicle generates Mode 01 PID data universally. Mode 06 adds continuous pass/fail margin data that standard scan tools collapse to a binary. The signal is already there — it just isn't being read.

3. **Real stakes.** Vehicle health directly affects safety and cost. Catching a developing coolant system issue or a degrading catalytic converter before a DTC is set has concrete value. The stakes make the HITL design meaningful, not decorative.

4. **Hardware accessible.** An ELM327 adapter (~$10–50) gives live signal access. Active hardware on hand — Zurich BT1, Mini VCI + Techstream, ESP32 CAN logger — means the pipeline can be validated against real vehicles, not just synthetic data.

---

## What Signal Looks Like

A valid signal is a **sustained, meaningful deviation** from expected operating parameters — one that persists across a drive cycle or recurs across sessions, and that correlates with at least one other related parameter.

Examples of real signal:
- Short-term fuel trim consistently +12% at idle across multiple cold starts → lean condition developing, likely vacuum leak or injector issue
- Mode 06 catalyst monitor at 0.91 efficiency (threshold: 0.90) → near-failure, weeks before a P0420 DTC is set
- Coolant temp rising slower than baseline during warm-up, paired with stat-temp at low normal → thermostat beginning to fail
- MAF reading low while engine load reads high → MAF contamination or air leak upstream

---

## What Noise Looks Like

Noise is a reading that looks anomalous in isolation but has an innocent explanation given context — operating state, warm-up phase, known transient behavior, or sensor electrical characteristics.

| Pattern | Why It's Noise |
|---|---|
| Fuel trim spike at cold start | Normal cold-start enrichment — ECM intentionally runs rich until O2 sensors reach operating temp |
| RPM flare at ignition | Normal starter and idle stabilization behavior |
| O2 sensor flat-line at startup | Sensor not yet at operating temperature (~300°C) — readings invalid until warmed |
| Single-sample coolant spike | Electrical transient or polling artifact — not a sustained reading |
| MAF reading near-zero at idle in park | Some vehicles report 0 or minimal MAF at true idle — not a fault |
| Mode 06 monitor "not run" status | Drive cycle not completed — monitor hasn't had conditions to run, not a failure |

---

## Separation Logic — Four Tiers

| Tier | Trigger | Response |
|---|---|---|
| **1 — Immediate** | Single reading crosses critical threshold (knock sensor active, coolant near boil, oil pressure drop) | Alert immediately — no pattern required |
| **2 — Pattern** | Multiple related sensors deviating together within a session | Correlate before flagging — require 2+ related PIDs |
| **3 — Persistence** | Same reading degrading across sessions over time | Flag as leading wear indicator — requires historical baseline |
| **4 — Cliff drop** | Value normal → suddenly at or past limit in one session | Points to sensor failure, wiring fault, or acute component failure |

Context applied to every reading: engine temp (warm vs. cold), run time elapsed, drive cycle state (idle, cruise, decel), and whether a relevant DTC or pending DTC is already present.
