# OBD2 Signal Interpretation — Logic, Limitations, and Future Vision

Created: 2026-06-12

This document captures working knowledge about interpreting OBD2 and MHD datalog signals correctly. It exists so these decisions don't get re-derived from scratch every time a new analysis feature is built.

---

## Core Principle: Many OBD2 Signals Are Only Meaningful With Operating Context

Some signals have completely different normal ranges depending on what the engine is doing. A mean across all operating conditions produces a number that doesn't describe any real condition — it's noise. This applies broadly across signal families, not just ignition timing.

**This is not a fixed rule with hardcoded thresholds.** The right approach is to research each signal's behavior and build interpretation logic appropriate to it. The three-bucket example below is illustrative, not prescriptive — actual classification thresholds and which signals need context should be validated against real data and PID documentation.

### Example: Operating Condition Classification

A rough three-bucket split that applies to load-dependent signals:

| Condition | RPM | ENGINE_LOAD | THROTTLE_POS |
|-----------|-----|-------------|--------------|
| Idle | < ~1000 RPM | < ~20% | < ~10% |
| Cruise | 1500–3500 RPM | 20–60% | 10–80% |
| WOT (full pull) | > 3500 RPM | > 85% | > 90% |

These thresholds need validation per engine family. Rows in transition between buckets should be excluded or handled carefully.

### Signals Where Context Matters

- **TIMING_ADV / TIMING_CYL1–6** — timing advance at idle is fundamentally different from WOT timing; comparing across conditions is misleading
- **MAP (manifold pressure) / boost** — nearly atmospheric at idle; meaningful only under load
- **FUEL_TRIM_ST_B1, FUEL_TRIM_LT_B1** — short-term trims behave differently at idle vs cruise; idle STFT drift can indicate vacuum leaks while cruise LTFT drift indicates fueling issues
- **LOAD_ABS** — by definition the segmentation variable; not useful as a raw trend metric

Signals that are relatively condition-independent (can be summarized across all conditions): coolant temp, battery voltage, O2 sensor steady-state readings, runtime.

### Research Needed

Before building condition-segmented analysis for any signal, the right approach is:
1. Research the PID's documented behavior (SAE J1979, MHD documentation, signal-specific guides)
2. Plot the raw signal against RPM and LOAD to observe actual behavior in the data
3. Validate classification thresholds against the observed distributions before using them in scoring

This is worth treating as a focused side project to ensure the logic is defensible, not just plausible.

---

## Ignition Timing on BMW N54/N55

### Why Generic `TIMING_ADV` (OBD2 PID 0x0E) Is Unreliable on BMW

The standard OBD2 formula for PID 0x0E is `A/2 - 64`, which maps the raw byte to a range of -64° to +63.5°. On BMW N54/N55 with MHD or CarScanner:

- At idle, this formula often returns highly negative values (e.g., -57.5°) that are clearly wrong
- Values reflect ECU-reported total timing, which may be the sum of base + corrections, and the encoding breaks at low-load conditions on this platform
- This caused a 0% ignition score in early testing: the healthy range floor of -5° was breached by bogus idle values

**Resolution**: Widened `TIMING_ADV` healthy range floor to -15° as a temporary workaround. The real fix is using MHD per-cylinder timing data when available.

### MHD Per-Cylinder Timing: The Right Signal

MHD logs `TIMING_CYL1` through `TIMING_CYL6` — the individual cylinder ignition timing correction applied by the ECU. These values represent the per-cylinder retard applied when the ECU detects knock (negative values = knock retard, 0 = no knock detected).

**Key interpretation rules:**

- `TIMING_CYL1` often represents all cylinders when knock is uniform (the ECU applies a global correction) — in these logs it can stand in for a fleet-wide "is there knocking?" signal
- Per-cylinder spread matters: if CYL1 = CYL2 = ... = CYL6, the correction is global; if one cylinder diverges significantly, that cylinder has a knock event
- The pipeline computes `KNOCK_RETARD` during ingest as `min(TIMING_CYL1...TIMING_CYL6)` — the worst-case (most-retarded) cylinder at any given moment. This is a **derived column from real logged values**, not invented or fabricated data. "Derived" means it's computed from real source columns using a defined formula.

**Scoring**: `KNOCK_RETARD = 0` for a session → Ignition score = 1.0 (100%). Any persistent negative correction degrades the score.

### Data Integrity Principle

**Never invent, impute, or fabricate data values.** If a signal is not in the log, it is absent — not estimated, not filled with a default. Outliers can be questioned and flagged, but their actual values must be preserved. Any derived column (like `KNOCK_RETARD`) must document the source columns and formula explicitly. There is no exception to this rule.

---

## MHD PID Logging — What We Have vs What's Available

### Default MHD PID Set

MHD ships with a default logging configuration. The existing 618 BMW session files were captured using this default set for:
- General performance monitoring
- Per-cylinder timing corrections (knock detection)
- Standard fuel/boost/coolant monitoring

The default set does **not** include exhaust/catalyst temperature sensors.

### Custom PIDs via MHD Config

MHD supports adding custom PIDs by editing its configuration file. Examples of useful PIDs that could be added:

- `CAT_TEMP_B1S1` — catalytic converter temperature, Bank 1 Sensor 1. **Available from MHD but not in existing logs.** Required for a meaningful Catalyst health score. Current demo shows "Catalyst" as N/A for this reason.
- Additional O2 sensor data (downstream O2)
- Wideband AFR if a wideband sensor is installed

**Future logging improvement**: When re-capturing data with the Dragy or custom solution, explicitly configure `CAT_TEMP_B1S1` and downstream O2. One drive cycle with CAT_TEMP_B1S1 logged provides significantly more diagnostic value than 484 sessions without it.

### Known Logging Gaps in Existing Data

| Signal | Gap | Impact |
|--------|-----|--------|
| `CAT_TEMP_B1S1` | Not in default PID set | Catalyst system shows N/A |
| Post-catalyst O2 | Not logged | Can't verify catalyst efficiency |
| MAP (boost) | Present but condition-unlabeled | Boost stats require segmentation |
| `LOAD_ABS` | Present | Sufficient for condition classification |

---

## Future Vision: Condition-Segmented Analysis UI

### The Idea

Instead of showing a single mean value for ignition timing or boost, show a **mini scatter plot segmented by operating condition**. Each data point is one row in the CSV. Points are colored by condition bucket (idle / cruise / WOT). Outliers (points beyond ±2σ within their condition bucket) are highlighted in a warning color.

**Value**: A healthy BMW at WOT should cluster tightly around 35–40° of timing advance. If a data point shows 28° at WOT with high load, that's meaningful knock retard. A plain mean of 32° across all conditions would mask this entirely.

### Implementation Notes (for when this gets built)

1. **Condition classification runs at ingest time** — add a `condition` column during `ingest_file()` or as a post-process step. Store alongside the row or derive on the fly for the visualization.

2. **Three scatter plots or one plot with color encoding** — three separate mini canvases (one per condition) are easier to read than one shared canvas with three colors.

3. **Outlier detection**: within each condition bucket, compute mean + stddev. Flag rows beyond ±2σ. For ignition timing, a negative outlier at WOT is the highest-severity signal (active knock retard during a pull).

4. **Signals that benefit most**: `TIMING_ADV` / `TIMING_CYL*`, `MAP_BOOST`, `LOAD_ABS` (sanity check), `FUEL_TRIM_ST_B1`.

5. **Signals where condition segmentation doesn't help**: `COOLANT_TEMP`, `BATTERY_VOLTAGE`, `RPM` (it's the classifier, not the metric).

---

## Data Acquisition Roadmap

### Current State

- **MHD**: Full-featured BMW-specific logger. Per-cylinder timing, custom PIDs via config. Existing 618 sessions from 2023–2025. Requires BMW + MHD app.
- **CarScanner / RepairSol2**: Generic OBD2 apps via ELM327 adapter. Inconsistent PID availability. **ELM327 is not the target solution going forward** — it was used for early testing and experimentation only.

### Target Hardware: Dragy OBD2 Device

The Dragy OBD2 logger (not the GPS Dragy device — the OBD2-specific Dragy device) is the target data acquisition hardware. It provides high-frequency OBD2 logging at 10–50 Hz, compared to ELM327's ~1–3 Hz. It outputs timestamped CSV rows structurally similar to MHD exports — already compatible with the MisfireAI ingest pipeline.

Key advantages over ELM327:
- Much higher logging frequency — enables per-maneuver analysis, not just session averages
- Consistent column output — not app-dependent like ELM327 + CarScanner combinations
- Works across makes/models (not BMW-only like MHD)

The Dragy OBD2 device was arriving for testing as of the time this document was written. Once tested: document exact column names, map to the canonical PID schema, confirm which PIDs are available at what frequency.

**What the acquisition strategy is NOT**: the solution is not ELM327 + any app. ELM327 inconsistency across apps and vehicles is a known problem that's been experienced directly. That path is closed.

### What Must Be Co-Logged

Any signal that requires condition-segmented analysis (timing, boost, fuel trims) is only meaningful if `RPM` + `LOAD_ABS` + `THROTTLE_POS` were logged in the same session at the same frequency. Future logging setups must treat these three as mandatory companion columns alongside any signal being analyzed.

---

## Related Files

- `tools/schema.py` — `HEALTHY_RANGES` dict, `_derive_knock_retard()` function
- `tools/mcp_server.py` — `ingest_file()`, `score_vehicle_health()`
- `scripts/generate_seed.py` — batch seed generation; shows how MHD CSVs are processed
- `data/sample/bmw-ije0s-seed.json` — 484-session seed; Feb 2023–Jun 2025
