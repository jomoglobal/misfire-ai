---
date: 2026-06-17
status: active
origin: docs/plans/2026-06-17-001-feat-dragy-deep-data-acquisition-plan.md
---

# U1: Deep-Capture PID Target Set

This document defines the canonical "what we need logged" spec that every acquisition path (Dragy, BLE, ESP32, or future) is measured against. It is the acceptance bar for the entire investigation.

---

## Acceptance Bar

An acquisition path is **only acceptable** if it:
1. Delivers **more PIDs than generic OBD2 Mode 01** — at minimum, at least one must-have deep PID from the table below.
2. Captures at a sample rate of **≥10 Hz** (matching or exceeding the existing Dragy VBO export).

Standard-BLE-only capture (generic Mode 01) fails criterion 1 by definition and is rejected.

---

## Must-Have Deep PIDs

These are the signals that make MisfireAI's analysis meaningful and that the existing ELM327/generic path **cannot** deliver.

| Canonical Name | Description | Unit | Current Availability |
|---|---|---|---|
| `STFT_B1` | Short term fuel trim bank 1 | % | mhd, car_scanner, carobd, cephasax, isay_gerard |
| `STFT_B2` | Short term fuel trim bank 2 | % | mhd, car_scanner, carobd, cephasax |
| `LTFT_B1` | Long term fuel trim bank 1 | % | car_scanner, carobd, isay_gerard |
| `LTFT_B2` | Long term fuel trim bank 2 | % | car_scanner, carobd, cephasax |
| `TIMING_CYL1`–`TIMING_CYL6` | Per-cylinder timing correction (knock retard) | degrees | **mhd only** |
| `KNOCK_RETARD` | Derived: min per-cylinder timing correction | degrees | **mhd only** (derived) |

**Notes:**
- Fuel trims (STFT/LTFT) are available via generic Mode 01 — they are reachable with ELM327. Their must-have status is about *rate*: at ≥10 Hz they show transient response; at ~1-3 Hz (ELM327) they are near-useless for drift analysis.
- Per-cylinder timing/knock is **manufacturer-specific** — it requires enhanced/OEM PID access and is the single highest-value gap in the current non-MHD dataset.

---

## Nice-to-Have Deep PIDs

Valuable but not required to declare a path successful.

| Canonical Name | Description | Unit | Current Availability |
|---|---|---|---|
| `CAT_TEMP_B1S1` | Catalyst temperature bank 1 sensor 1 | °C | carobd, isay_gerard |
| `CAT_TEMP_B1S2` | Catalyst temperature bank 1 sensor 2 | °C | carobd only |
| `O2_VOLT_B1S2` | Downstream O2 voltage bank 1 sensor 2 | V | isay_gerard only |
| `O2_LAMBDA_B1S1` | Wideband equivalence ratio upstream | lambda | cephasax, isay_gerard |
| `LTFT_B1` / `LTFT_B2` | Long term fuel trims (if not already captured) | % | see above |

---

## Mandatory Companion PIDs (Condition Segmentation)

These must be co-logged at the same frequency as any deep PID. Without them, the deep signals cannot be segmented by operating condition (idle / cruise / WOT), which renders trend analysis meaningless.

See `docs/brainstorms/2026-06-12-obd2-signal-interpretation.md` for the full condition-segmentation rationale.

| Canonical Name | Description | Unit | Dragy VBO Available? |
|---|---|---|---|
| `RPM` | Engine RPM | rpm | ✅ (`rpm-obd`) |
| `LOAD` | Calculated engine load | % | ✅ (`engine_load-obd`) |
| `THROTTLE` | Throttle position | % | ✅ (`throttle_pos-obd`) |
| `MAF` | Mass airflow | g/s | ✅ (`manifold_flow-obd`) |
| `ECT` | Engine coolant temperature | °C | ✅ (`coolant_temp-obd`) |
| `TIMING_ADV` | Generic timing advance | degrees | ✅ (`timing_advance-obd`) |

All 6 companion PIDs are present in the existing Dragy VBO export. The VBO adapter (U2) captures the full companion set at 10 Hz today. The investigation (U3–U5) is about adding the deep PIDs on top.

---

## What the Dragy VBO Export Delivers Today

The analyzed sample (`data/sample/dragylap_20260606_162501_HF Perris to Home.vbo`, 14,952 rows, 10.0 Hz) contains:

| Raw VBO Column | Canonical Name | Notes |
|---|---|---|
| `rpm-obd` | `RPM` | ✅ companion |
| `speed-obd` | `VSS` | — |
| `coolant_temp-obd` | `ECT` | ✅ companion |
| `intake_temp-obd` | `IAT` | — |
| `manifold_flow-obd` | `MAF` | ✅ companion |
| `throttle_pos-obd` | `THROTTLE` | ✅ companion |
| `engine_load-obd` | `LOAD` | ✅ companion |
| `timing_advance-obd` | `TIMING_ADV` | ✅ companion |
| `velocity` | (GPS speed, km/h) | skip — duplicate of `speed-obd` |
| `sats`, `lat`, `long`, `heading`, `height`, `acceleration-obd` | GPS/motion | skip — no canonical home |

**Verdict on current VBO:** All companion PIDs present, no must-have deep PIDs (no fuel trims, no per-cylinder timing). Equivalent to generic Mode 01 for diagnostic depth.

---

## Pass/Fail Bar for U3–U5

A Dragy investigation path **passes** if it delivers any of:
- `STFT_B1` + `STFT_B2` at ≥10 Hz, OR
- Any per-cylinder timing correction (`TIMING_CYL1`–`TIMING_CYL6`) at any rate

A path that delivers only the same 8 channels the VBO already provides fails the acceptance bar (R2).

---

## Mapping to SIGNAL_SCHEMA

All canonical names above exist in `tools/schema.py` `SIGNAL_SCHEMA`. The `dragy` source will be added to each signal's `source_availability` in U2 — initially reflecting what the VBO export provides (companion PIDs) and updated as investigation units report deeper PID captures.
