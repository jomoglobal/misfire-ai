# OBD2 Vehicle Health Advisor — Monitoring Plan

**Last updated:** 2026-04-15  
**Tracing backend:** Arize Phoenix (dual-account: personal + Sravan/euler)  
**OTel service name:** `obd2-vehicle-health-advisor`

---

## Overview

Two monitoring surfaces:

1. **Eval harness** (`evals/run_synthetic_evals.py`) — offline quality gates run against synthetic dataset, traces exported to Phoenix with structured `eval.*` attributes.
2. **Production agent** (`lib/agent.ts`) — live Next.js app, every `runDiagnosticAgent` call creates an `obd2.diagnostic` span in Phoenix.

This plan covers what to watch, at what cadence, and what to do when signals degrade.

---

## 1. Eval Quality Metrics (Offline)

Run evals after every prompt or vehicle-config change. Pass/fail threshold is **6/10** (see `docs/judge-validation.md` for rationale).

### Minimum acceptable thresholds (per prompt version)

| Scenario Tag | Min Pass Rate | Rationale |
|---|---|---|
| `diagnosis_accuracy` | ≥ 67% (8/12) | Current v2 baseline. Regression if drops below 50% (6/12). |
| `urgency_calibration` | ≥ 75% (6/8) | Urgency errors are directly user-facing. |
| `data_completeness` | ≥ 80% (4/5) | Data gap detection is mechanical — should be reliable. |
| **Overall** | ≥ 72% (18/25) | v2 baseline is 52% at threshold 7; ~68% expected at threshold 6. |

### Score breakdown to watch

Five sub-scores (0–2 each) are tracked as `eval.score.*` span attributes:

| Sub-score | What it measures | Watch for |
|---|---|---|
| `urgency_correct` | Correct urgency tier assigned | Drop signals prompt drift or model regression |
| `root_cause_identified` | Primary fault named correctly | Most diagnostic value — weight heavily |
| `bogus_value_handled` | 0xFF rollover artifacts flagged, not diagnosed | Must be 2/2 on bogus-value cases |
| `data_gap_noted` | Missing expected PIDs called out | Must be 2/2 on sparse-data cases |
| `vehicle_quirk_cited` | Vehicle-specific patterns cited (HPFP, SAI, EGR) | Most likely to regress if vehicle configs change |

**Alert trigger:** Any sub-score drops below 50% mean across its scenario type → investigate prompt or vehicle config.

---

## 2. Production Trace Monitoring (Phoenix)

Every live diagnosis call creates an `obd2.diagnostic` span. Monitor the following:

### 2.1 Latency

| Metric | Target | Alert threshold |
|---|---|---|
| p50 latency | < 4s | > 6s |
| p95 latency | < 8s | > 12s |
| Error rate | < 2% | > 5% |

Primary latency driver: GPT-4o completion. Watch for OpenAI API degradation independently.

### 2.2 Span Attributes to Query in Phoenix

All production spans carry these attributes (set in `lib/agent.ts`):

```
vehicle.id       — tundra-2007 | bmw-335i-2009 | honda-fit-2015
vehicle.make     — Toyota | BMW | Honda
vehicle.model    — Tundra | 335i | Fit
vehicle.year     — 2007 | 2009 | 2015
scenario         — free-text from caller
student_name     — jmontague (or other)
```

Useful Phoenix queries:
- Filter by `vehicle.id` to see per-vehicle volume and error rates
- Filter `status_code = ERROR` to catch OpenAI or preprocessing failures
- Track `scenario` distribution to see which use cases are most common

### 2.3 Preprocessor Warning Rate

The `preprocessor.ts` emits warnings for:
- `0xFF` rollover values (ECT=255°C, MAP=255 kPa, STFT=-96%)
- Startup artifacts (first-poll spikes)
- Out-of-range sensor readings

These warnings are returned in `AgentOutput.warnings` and passed to the LLM as context. A high warning rate on production data indicates:
- Poor OBD2 adapter (ELM327 firmware issues)
- User is logging raw unfiltered data
- New vehicle type with unexpected PID encoding

**To add:** Log `warnings.length` as a span attribute (`preprocessor.warning_count`) so Phoenix can surface high-artifact snapshots.

---

## 3. Data Quality Checks (Datalog Ingestion)

When real datalogs are uploaded (Car Scanner CSV, MHD CSV), validate before ingestion:

### Required checks

| Check | Pass condition | Failure action |
|---|---|---|
| **Minimum duration** | ≥ 5 minutes of logging | Warn: insufficient warm-up coverage |
| **PID coverage** | ≥ 6 of vehicle's `expectedPIDs` present | Warn: data gap analysis limited |
| **ECT warm** | ECT mean > 75°C (for non cold-start analysis) | Flag as cold-start-only if not |
| **Dropout detection** | No gap > 60s between consecutive rows | Warn: Bluetooth/adapter dropout; note affected time range |
| **Rollover artifact rate** | < 5% of readings are 0xFF artifacts | Flag adapter quality issue if exceeded |
| **MAF present (MAF vehicles)** | PID 0110 present with std > 0 | Warn: load/fuel analysis incomplete |
| **STFT/LTFT both banks (dual-bank)** | Both B1 and B2 trim pairs present | Warn: bank comparison impossible |

### Known data quality issues (per vehicle)

| Vehicle | Known issues | Mitigation |
|---|---|---|
| **2007 Tundra 1GR-FE** | ELM327 drops MAF (0110), upstream O2 (0114/011B), STFT B2 (0108) | These are in `inaccessiblePIDs` — suppress missing-PID warnings |
| **2007 Tundra 1GR-FE** | 16-minute BT dropout during mid-drive | Switch to WiFi OBD2 adapter |
| **2009 BMW 335i N54** | Car Scanner polls at ~1–2 Hz vs MHD at 11+ Hz | Prefer MHD for WOT/boost analysis |
| **2009 BMW 335i N54** | Module Voltage consuming 40% of Car Scanner polling slots | Remove Module Voltage from PID list |
| **2015 Honda Fit L15B** | 010D (vehicle speed) always returns 0 via generic OBD2 | In `inaccessiblePIDs` — expected |
| **2015 Honda Fit L15B** | MAF drops at WOT with 9+ PIDs logged | Reduce to ≤ 8 PIDs for WOT captures |

---

## 4. Recommended PID Lists (Per Vehicle)

Condensed from datalog analysis. Priority order within each vehicle.

### 2007 Toyota Tundra 1GR-FE (ELM327 / Car Scanner)

| Priority | PID | Name | Notes |
|---|---|---|---|
| 1 | 0107 | LTFT B1 | Core health signal |
| 2 | 0109 | LTFT B2 | Core health signal |
| 3 | 0106 | STFT B1 | Real-time correction |
| 4 | 0105 | ECT | Warm-up state |
| 5 | 010C | RPM | Load context |
| 6 | 0104 | Engine load | Load context |
| 7 | 010F | IAT | Air density / MAF cross-check |
| 8 | 0115 | O2 B1S2 (downstream) | Cat health |
| 9 | 011C | O2 B2S2 (downstream) | Cat health |

**Omit:** 0110 (MAF — unreachable), 0108 (STFT B2 — unreachable), 0114/011B (upstream O2 — unreachable), 010D (Module Voltage — wastes slots).

### 2009 BMW 335i N54 (Car Scanner — idle/city)

| Priority | PID | Name | Notes |
|---|---|---|---|
| 1 | 0107 | LTFT B1 | Core health signal |
| 2 | 0109 | LTFT B2 | Core health signal |
| 3 | 010A | Fuel pressure | HPFP health — critical for N54 |
| 4 | 0105 | ECT | Warm-up state |
| 5 | 0110 | MAF | Fueling calculation |
| 6 | 010B | MAP | Boost pressure |
| 7 | 010F | IAT | Charge air temp (charge pipe integrity) |
| 8 | 010C | RPM | Load context |

**Use MHD instead** for WOT pulls, knock analysis, per-cylinder data, and HPFP low-pressure feed pressure.  
**Omit:** Module Voltage (wastes 40% of polling slots on Car Scanner).

### 2015 Honda Fit L15B (Car Scanner)

| Priority | PID | Name | Notes |
|---|---|---|---|
| 1 | 0107 | LTFT B1 | Core health signal |
| 2 | 010B | MAP | Primary load sensor (MAP-based) |
| 3 | 0105 | ECT | Warm-up state |
| 4 | 0106 | STFT B1 | Real-time correction |
| 5 | 012C | Commanded EGR | EGR system health |
| 6 | 012D | EGR error | EGR deviation |
| 7 | 0110 | MAF | Fueling cross-check |
| 8 | 010C | RPM | Load context |

**Limit to 8 PIDs** to maintain adequate MAF polling rate at WOT.

---

## 5. Cadence and Ownership

| Activity | Cadence | Owner |
|---|---|---|
| Run synthetic evals (`run_synthetic_evals.py`) | After every prompt or vehicle-config change | jmontague |
| Review Phoenix traces for production errors | Weekly | jmontague |
| Capture new Tundra datalog (WiFi adapter, correct 9 PIDs) | Next opportunity | jmontague |
| Capture BMW WOT pull via MHD (boost, knock, HPFP rail pressure) | Next opportunity | jmontague |
| Expand synthetic dataset (new scenarios from real datalog findings) | As new faults discovered | jmontague |
| Re-run judge validation after prompt changes > minor | After major prompt revisions | jmontague |

---

## 6. Open Issues

- [ ] Add `preprocessor.warning_count` as a span attribute in `lib/agent.ts` so Phoenix can surface high-artifact snapshots
- [ ] Write `scripts/parse_carscanner_csv.ts` — convert Car Scanner horizontal CSV to agent snapshot JSON (pivot sparse format, drop artifacts, compute min/max/mean/std)
- [ ] Capture Tundra datalog with WiFi OBD2 adapter (eliminate BT dropout)
- [ ] Investigate why HONDA_001 (EGR stuck open) scored only 6/10 despite clear EGR signals — likely `vehicle_quirk_cited` and `data_gap_noted` sub-scores failing; refine prompt EGR section
- [ ] Lower eval pass threshold from 7/10 to 6/10 in `run_synthetic_evals.py` based on judge validation findings

