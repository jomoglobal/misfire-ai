# OBD2 Dataset Research
*MisfireAI · Last updated May 2026*

Reference document for evaluating public OBD2 / vehicle telemetry datasets as supplemental
data sources. MisfireAI's primary data is real MHD logs (477 BMW 335i sessions). This doc
covers what's publicly available and where each source fits.

---

## Decision Framework

For MisfireAI, a dataset is useful if it provides:
- **Fuel trims** (STFT/LTFT — Mode 01 PIDs 0x06–0x09) — core diagnostic signal
- **O2 sensor data** — essential for fuel system analysis
- **MAF or MAP** — required for load and fueling calculations
- **Coolant temp + RPM** — operating context
- **DTCs** — optional but valuable for labeled fault scenarios
- **Mode 06 monitor margins** — ideal but essentially absent from all public datasets

Frequency: 1 Hz is acceptable for session analysis. 10Hz+ preferred for transient events.

---

## Tier 1 — Confirmed Useful (Real OBD2 + Fuel Trims Verified)

---

### 1. OBD-II & CAN-Based Driving Behavior Dataset
- **Source:** Kaggle — Isay Gerard Ozamora
- **URL:** https://www.kaggle.com/datasets/isaygerardozamora/obd-ii-and-can-based-driving-behavior-dataset
- **Vehicle:** KIA Soul (1 vehicle, 10 drivers, 34 km route)
- **Size:** 65,535 rows
- **Format:** CSV · 1 Hz
- **STFT/LTFT:** ✅ Confirmed — Short fuel trim B1, Long fuel trim B1, Short fuel trim B2, Long fuel trim B2
- **O2 Sensors:** Unknown
- **MAF/MAP:** Unknown (50+ parameters — likely present)
- **DTCs:** Not documented
- **Mode 06:** ❌ Not present
- **License:** Published via Springer Nature / PMC Open Access
- **Notes:** Associated academic paper available (PMC10198028). Single vehicle limits make/model diversity. Good for fuel trim pattern analysis.
- **Verdict:** Best available public dataset for fuel trim coverage. Download and inspect column list.

---

### 2. carOBD — Toyota Etios OBD Data
- **Source:** GitHub — eron93br (same author as Kaggle obd2data)
- **URL:** https://github.com/eron93br/carOBD
- **Kaggle mirror:** https://www.kaggle.com/datasets/eron93br/obd2data
- **Vehicle:** Toyota Etios 2014, 1496 CC (1 vehicle)
- **Size:** Unknown rows; organized by driving mode (idle, drive, live, ufpe, long)
- **Format:** CSV · 1 Hz
- **Columns (27 PIDs):** Fuel trim values confirmed (STFT B1, LTFT B1); engine coolant temp, RPM, load, speed, throttle, MAF, O2 sensors
- **STFT/LTFT:** ✅ Confirmed
- **O2 Sensors:** ✅ Present
- **MAF:** ✅ Present
- **DTCs:** Unknown
- **Mode 06:** ❌ Not present
- **License:** Open — request citation of associated master's thesis
- **Notes:** Clean academic dataset. Includes Arduino firmware + Python analysis scripts. Single vehicle, single-bank engine. Useful as a third vehicle type alongside BMW 335i and Honda Fit.
- **Verdict:** Good supplemental dataset. Small scope but clean and well-documented.

---

## Tier 2 — Potentially Useful (Real OBD2, Fuel Trim Status Unconfirmed)

---

### 3. Levin Vehicle Telematics
- **Source:** Kaggle + GitHub — YunSolutions
- **Kaggle:** https://www.kaggle.com/datasets/yunlevin/levin-vehicle-telematics
- **GitHub:** https://github.com/YunSolutions/levin-openData
- **Vehicles:** ~30 vehicles, 4-month collection
- **Format:** CSV, SQLite3, ZIP · OBD @ 1 Hz, accelerometer @ 25 Hz
- **Confirmed PIDs:** Coolant temp, engine load, intake air temp, MAP, MAF, RPM, throttle, timing advance, OBD speed, GPS speed, battery voltage, **DTCs included**
- **STFT/LTFT:** ❓ Not explicitly documented — needs column inspection
- **O2 Sensors:** Unknown
- **DTCs:** ✅ Confirmed present
- **Mode 06:** ❌ Not present
- **License:** Creative Commons BY-NC-SA (non-commercial only)
- **Notes:** Best multi-vehicle public dataset. DTCs make it useful for fault scenario labeling. Proprietary LEVIN OBD dongle — may affect PID coverage. Fuel trim status is the key unknown.
- **Verdict:** High value if STFT/LTFT confirmed on inspection. Best source for multi-vehicle diversity.

---

### 4. Driving Datasets OBD-II/CAN-BUS
- **Source:** Kaggle — Anwar Mehmood Sohail (University of Malaya)
- **URL:** https://www.kaggle.com/datasets/anwarmehmoodsohail/driving-datasets-obd-iican-bus
- **Vehicles:** Multiple (exact count undocumented)
- **Format:** Unknown — requires Kaggle access
- **Confirmed PIDs:** Fuel consumption, throttle, RPM, gear, steering angle, road gradient, acceleration, torque, load, intake air pressure, coolant temp, vehicle speed, brake
- **STFT/LTFT:** ❓ Unknown — not confirmed in documentation
- **DTCs:** Unknown
- **Mode 06:** ❌ Not present
- **License:** Unknown
- **Notes:** Research-backed. Unusual signals (steering angle, gear position) suggest richer CAN bus access beyond standard OBD2. Worth downloading to inspect.
- **Verdict:** Inspect column list before committing. May be more CAN-oriented than OBD2.

---

### 5. OBD Dataset
- **Source:** Kaggle — dommatap
- **URL:** https://www.kaggle.com/datasets/dommatap/obd-dataset
- **Vehicles:** Multiple (4 drivers, 3 testbeds, master's research)
- **Format:** CSV
- **Confirmed PIDs:** RPM, engine load, speed, MAP, MAF, throttle position, timing advance
- **STFT/LTFT:** ❓ Not confirmed
- **O2 Sensors:** Unknown
- **DTCs:** Unknown
- **Mode 06:** ❌ Not present
- **License:** Unknown
- **Notes:** Real driving data, academic origin. Column inspection needed.
- **Verdict:** Moderate — real data, unknown fuel trim coverage.

---

### 6. cephasax OBD-II Datasets
- **Source:** Kaggle + GitHub — cephasax (UFRN master's research)
- **Kaggle:** https://www.kaggle.com/datasets/cephasax/obdii-ds3
- **GitHub:** https://github.com/cephasax/OBDdatasets
- **Vehicles:** Three experiments: 19 drivers, 4 drivers, 14 drivers
- **Format:** CSV
- **Confirmed PIDs:** Engine coolant temp, RPM, engine load, speed, MAP, MAF, throttle, timing advance (8 PIDs confirmed)
- **STFT/LTFT:** ❓ Not confirmed — documentation incomplete ("will be detailed soon")
- **DTCs:** Unknown
- **Mode 06:** ❌ Not present
- **License:** Unknown
- **Notes:** Multi-experiment, multiple drivers. Full Portuguese thesis available via UFRN. Incomplete documentation is the main uncertainty.
- **Verdict:** Worth inspecting — multi-driver data useful for behavioral diversity.

---

### 7. X-CANIDS Dataset (Hyundai Sonata)
- **Source:** IEEE DataPort
- **URL:** https://ieee-dataport.org/open-access/x-canids-dataset-vehicle-signal-dataset
- **Vehicle:** Hyundai LF Sonata 2017 e-VGT (1 vehicle)
- **Size:** 688 decoded signals; raw CAN ~4.44 GB, decoded ~1.11 GB
- **Format:** Parquet (decoded) + raw CAN
- **STFT/LTFT:** ❓ 688 signals decoded via .dbc file — may include OBD PIDs but not confirmed
- **DTCs:** Not documented
- **Mode 06:** Unknown
- **License:** IEEE DataPort (free for IEEE members)
- **Notes:** Decoded via manufacturer .dbc file — this may mean richer signal coverage than standard OBD2. Intrusion detection focus but signal breadth is notable. Requires inspection.
- **Verdict:** Potentially very useful if 688 signals include fuel trims. Needs access to verify.

---

### 8. CANdid — Annotated Multi-Vehicle CAN Dataset (USENIX 2025)
- **Source:** USENIX Vehicle Security Symposium 2025
- **URL:** https://www.usenix.org/conference/vehiclesec25/presentation/howson
- **Vehicles:** 10 vehicles, multiple manufacturers
- **Format:** CAN format (raw)
- **STFT/LTFT:** ❓ Unknown — CAN data, OBD decoding status unclear
- **DTCs:** Unknown
- **Mode 06:** Unknown
- **License:** Open access (USENIX)
- **Notes:** Very recent (2025). Multi-manufacturer, real + controlled conditions, includes GPS and driver video. Could be the most diverse dataset available — but it's CAN-level data, not pre-decoded OBD2 PIDs.
- **Verdict:** Watch this one. If a .dbc decode is available, 10-vehicle multi-manufacturer coverage is extremely valuable.

---

### 9. telemetry-obd Logger + Data
- **Source:** GitHub — thatlarrypearson
- **URL:** https://github.com/thatlarrypearson/telemetry-obd
- **Vehicles:** Multiple (organized by VIN, Raspberry Pi-based collection)
- **Format:** Line-delimited JSON (one record per sample, ISO-8601 timestamps)
- **STFT/LTFT:** ❓ Config-dependent — user selects PIDs; fuel trims possible but not guaranteed
- **DTCs:** Config-dependent
- **Mode 06:** Config-dependent
- **License:** MIT
- **Notes:** This is primarily a logging tool, but the repo includes sample data from multiple vehicles. JSON format with per-record completeness is interesting for MisfireAI's ingest layer. Known issues: dropped VIN characters, CVN validity concerns.
- **Verdict:** Sample data worth inspecting. JSON format maps well to MisfireAI's normalized schema.

---

## Tier 3 — Reference Only (Not Driving Data)

---

### 10. OBDb — Open OBD2 Signal Database
- **URL:** https://github.com/OBDb
- **What it is:** Community-maintained database of Mode 01 PID definitions + manufacturer-specific extensions
- **Coverage:** 150+ Mode 01 PIDs including STFT (0x06, 0x08), LTFT (0x07, 0x09), plus DTC definitions
- **Format:** JSON/CSV
- **License:** Open source
- **Use for MisfireAI:** PID decode reference, threshold lookup, formula validation. Essential reference — not a driving dataset.

---

### 11. CSS Electronics OBD2 Sample Data + DBC
- **URL:** https://www.csselectronics.com/pages/obd2-pid-table-on-board-diagnostics-j1979
- **What it is:** Free OBD2 DBC file (150+ Mode 01 PIDs) + small sample log (Audi A4)
- **Format:** MF4 (ASAM MDF4) — industry standard for automotive logging
- **License:** Free non-commercial
- **Use for MisfireAI:** DBC decode reference. Sample data minimal but real.

---

## Not Recommended

| Dataset | Reason |
|---|---|
| ROAD Dataset (ORNL) | Raw CAN bus, intrusion detection — no decoded OBD PIDs |
| CAN-MIRGU (UCI) | Raw CAN bus, attack scenarios — no OBD diagnostics |
| SynCAN (ETAS) | Synthetic data, no real vehicle parameters |
| KIT Automotive Dataset | Only 10 PIDs, no fuel trims |
| hayatu4islam Automotive_Diagnostics | Only 10 PIDs, no fuel trims |
| CrySyS CAN Traffic Logs | Attack-focused, limited availability |

---

## Critical Gap Across All Sources

**Mode 06 data is absent from every public dataset.** Mode 06 (On-Board Monitor Test Results) is where MisfireAI's predictive scoring lives — the margin between a measured monitor value and its pass/fail threshold. No public dataset provides this. The only sources for Mode 06 data are:

1. Live capture via your own hardware (ELM327, Dragy, Techstream)
2. Proprietary scan tool exports (Techstream, ISTA, FORScan)
3. Real vehicle sessions you collect yourself

This is actually a competitive advantage for MisfireAI — it uses data that no existing academic dataset captures.

---

## Priority Download List

When ready to pull data:

1. **carOBD (GitHub)** — small, clean, open license, fuel trims confirmed. Start here.
2. **Isay Gerard OBD-II & CAN (Kaggle)** — largest confirmed fuel trim dataset. Inspect column list.
3. **Levin Vehicle Telematics (GitHub)** — multi-vehicle, DTCs included. Inspect for STFT/LTFT.
4. **cephasax OBD-II (Kaggle)** — multi-driver, real data. Inspect for fuel trims.
5. **telemetry-obd sample data (GitHub)** — JSON format, multi-vehicle. Inspect schema.

---

## Dragy Notes (Pending)

Dragy OBD2 logger stores data as timestamped CSV rows — structurally similar to MHD exports.
High-frequency logging (10–50 Hz vs ELM327's 1–3 Hz). Once device arrives:
- Document exact column names and units
- Map to MisfireAI normalized PID schema
- Confirm STFT/LTFT availability at high frequency
- Add to this doc

---

*Sources: Kaggle, GitHub, IEEE DataPort, UCI ML Repository, USENIX VehicleSec 2025, Zenodo, ORNL, CSS Electronics*
