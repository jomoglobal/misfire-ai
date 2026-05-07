# Signal Decision
*MisfireAI · May 2026*

---

## Signal Type

**Reactive Signal** — sensor anomalies, threshold breaches, system state changes.

The vehicle's OBD2 system continuously produces a stream of parametric data (PIDs) across dozens of systems. This pipeline treats that stream as a reactive signal: something to monitor, score, and act on — not just store.

---

## Why This Signal

1. **Domain depth.** This signal is built on a foundation most developers don't have: an automotive degree, ASE certification, prior shop ownership, and years of hands-on diagnostic work. The difference between a lean condition at idle and a lean condition under boost load, what a timing retard pattern actually means, why a charge pipe failure looks identical to an injector fault in raw trim data — that's not research, that's recalled experience. This isn't a signal chosen for convenience; it's a domain with deep, firsthand expertise behind every design decision.

2. **Rich, continuous, and underutilized.** Every 1996+ US vehicle generates Mode 01 PID data universally. Fuel trim trends, O2 patterns, MAF correlation, and coolant baselines tell a layered story across sessions. Beyond Mode 01, Mode 06 adds continuous pass/fail margin data that standard scan tools collapse to a binary — a catalyst at 91% of its threshold passes every scanner on the market, but the margin is already there waiting to be read. The signal exists at multiple depths; most tools only read the surface.

3. **Real stakes.** Vehicle health directly affects safety and cost. Catching a developing coolant system issue or a degrading catalytic converter before a DTC is set has concrete value. The stakes make the HITL design meaningful, not decorative.

4. **Hardware accessible — and deliberately affordable.** The long-term goal is a replicable stack anyone can build cheaply. Current hardware under test spans the full range from consumer to professional:

   | Device | Cost range | Use |
   |---|---|---|
   | Zurich BT1 (Harbor Freight) | ~$50 | Generic OBD2, Mode 01, Car Scanner compatible |
   | MHD Orange Dongle | ~$100 | BMW-specific, high-freq, primary data source |
   | Mini VCI + Techstream | ~$20 cable | Toyota/Lexus deep access, manufacturer PIDs |
   | BMW K+DCAN Cable | ~$15 cable | BMW K-Line/D-CAN, INPA/ISTA compatible |
   | Dragy OBD2 Logger | ~$100 | High-freq (10–50Hz), arriving for testing |
   | ESP32 + CAN transceiver | ~$15–25 DIY | Target build — raw CAN access, replicable budget hardware |

   The target end state is an ESP32-based logger that costs under $25 in parts, pulls raw CAN data at high frequency, and runs MisfireAI's capture agent locally.

---

## What Signal Looks Like

A valid signal is a **sustained, meaningful deviation** from expected operating parameters — one that persists across a drive cycle or recurs across sessions, and that correlates with at least one other related parameter.

Examples of real signal:
- LTFT drifting from +3% → +7% → +11% across 20 sessions at idle → lean condition developing, weeks before a DTC is set
- Coolant temp reaching operating temp 40 seconds slower than the 30-session baseline, same ambient conditions → thermostat beginning to fail
- MAF reading low while engine load reads high → MAF contamination or air leak upstream
- Both banks lean simultaneously with low MAF → vacuum leak or restricted air filter
- Mode 06 catalyst monitor at 0.91 efficiency with threshold 0.90 → one drive cycle from failure *(requires Mode 06-capable hardware — see architecture.md)*

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
