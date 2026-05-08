# OBD2 Dataset Research
*MisfireAI · Last updated May 2026*

Reference document for evaluating public OBD2 / vehicle telemetry datasets as supplemental
data sources. MisfireAI's primary data is real MHD logs (477 BMW 335i sessions). This doc
covers what's publicly available and where each source fits.

---

## Dataset Status Summary

| # | Dataset | Status | Rows | STFT/LTFT | O2 | DTCs | Cat Temp | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | carOBD (eron93br) | ✅ In use | 304k | ✅ B1 only | ❌ | ❌ | ✅ | Toyota Etios, single-bank, MAP-based |
| 2 | cephasax OBD-II | ✅ In use | 70k | ✅ B1+B2 | ❌ | ✅ real codes | ❌ | Multi-make Brazil, only dataset with real DTCs |
| 3 | Isay Gerard OBD-II | ✅ In use | 1.1M | ✅ B1 only | ✅ | ❌ | ✅ | KIA Soul, best O2 + timing advance coverage |
| 4 | Levin Telematics | ❌ Skipped | ~30 veh | ❌ absent | ❌ | ⚠️ count only | ❌ | No fuel trims; data behind auth-gated external links |
| 5 | telemetry-obd | ❌ Skipped | none | — | — | — | — | Tool only — no downloadable sample data in repo |
| 6 | Isay Gerard (Kaggle) | same as #3 | — | — | — | — | — | Same dataset, different entry point |
| 7 | Anwar Mehmood (Kaggle) | ❌ Skipped | 374 rows | ✅ B1 | ❌ | ✅ some | ❌ | Too small; JSON-in-CSV format; GPS files dominate |
| 8 | dommatap OBD (Kaggle) | ❌ Skipped | unknown | ❓ | ❓ | ❓ | ❓ | Dataset deleted or made private — URL returns 404 |
| 9 | X-CANIDS (Hyundai Sonata) | ⏳ Hold | 688 signals | ❓ | ❓ | ❌ | ❓ | IEEE DataPort access needed; CAN-decoded |
| 10 | CANdid (USENIX 2025) | ⏳ Hold | 10 vehicles | ❓ | ❓ | ❓ | ❓ | Raw CAN; needs .dbc decode to be useful |
| 11 | OBDb signal database | ✅ Reference | — | — | — | — | — | PID definitions + thresholds, not driving data |
| 12 | CSS Electronics sample | ✅ Reference | small | — | — | — | — | DBC file + Audi A4 sample; format reference |

**In use = downloaded, inspected, confirmed columns, available in `data/external/`**

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

## Tier 1 — Confirmed Useful (Real OBD2 + Fuel Trims Verified, Inspected)

---

### 1. carOBD — Toyota Etios OBD Data ✅ DOWNLOADED & INSPECTED
- **Source:** GitHub — eron93br
- **URL:** https://github.com/eron93br/carOBD
- **Kaggle mirror:** https://www.kaggle.com/datasets/eron93br/obd2data
- **Local path:** `data/external/carOBD/`
- **Vehicle:** Toyota Etios 2014, 1496 CC, single-bank, MAP-based, Brazil
- **Size:** 129 CSV files · 304,304 rows · 85 MB
- **File modes:** `drive` (13 files, road), `idle` (47, parked engine on), `live` (39, work→home route), `long` (12, long trips), `ufpe` (18, low-speed campus)
- **Format:** CSV · 1 Hz · no timestamp column (row = 1 second)
- **Confirmed columns (27):**

| Column | MisfireAI relevance |
|---|---|
| ENGINE_RPM | ✅ Core |
| ENGINE_LOAD | ✅ Core |
| COOLANT_TEMPERATURE | ✅ Core |
| SHORT_TERM_FUEL_TRIM_BANK_1 | ✅ Core — range: -7.8% to +11.7% in drive1 |
| LONG_TERM_FUEL_TRIM_BANK_1 | ✅ Core — range: -5.5% to +0.8% in drive1 |
| INTAKE_MANIFOLD_PRESSURE | ✅ Core (MAP-based engine) |
| MAF | ✅ Core |
| INTAKE_AIR_TEMP | ✅ Core |
| VEHICLE_SPEED | ✅ Context |
| THROTTLE / ABSOLUTE_THROTTLE_B | ✅ Context |
| TIMING_ADVANCE | ✅ Useful |
| CATALYST_TEMP_BANK1_SENSOR1 | ✅ Useful — actual cat temp values |
| CATALYST_TEMP_BANK1_SENSOR2 | ✅ Useful |
| FUEL_AIR_COMMANDED_EQUIV_RATIO | ⚠️ All zeros in inspected file — may be unsupported |
| ENGINE_RUN_TIME | ✅ Context |
| FUEL_TANK | ✅ Context |
| DISTANCE_TRAVELED_WITH_MIL_ON | ✅ DTC indicator |
| TIME_RUN_WITH_MIL_ON | ✅ DTC indicator |
| WARM_UPS_SINCE_CODES_CLEARED | ⚠️ Always 255 — likely rollover artifact |

- **STFT/LTFT:** ✅ Both confirmed, single bank only (single-bank engine)
- **O2 Sensors:** ❌ Not in column list — absent from this vehicle's OBD2 export
- **DTCs:** ⚠️ No DTC codes column — MIL distance/time present as indirect indicators
- **Mode 06:** ❌ Not present
- **Data quality notes:** FUEL_AIR_COMMANDED_EQUIV_RATIO all zeros in at least one file. WARM_UPS always 255 (rollover). No timestamp — rows are sequential seconds only. No Bank 2 trims (single-bank engine by design).
- **License:** Open — cite IEEE paper (DOI: 10.1109/8891367)
- **Verdict:** ✅ Clean, well-structured, real fuel trim data. Good as third vehicle type (Toyota, MAP-based, single-bank). Best starting point for building the ingest parser.

---

### 2. cephasax OBD-II Datasets ✅ DOWNLOADED & INSPECTED
- **Source:** GitHub — cephasax (UFRN master's research, Brazil)
- **URL:** https://github.com/cephasax/OBDdatasets
- **Local path:** `data/external/cephasax-OBDdatasets/`
- **Vehicles:** Multiple makes — Chevrolet, Toyota, VW, Peugeot, Fiat, Renault, Citroën, Nissan, Honda, Ford. Years 2003–2016.
- **Size:** 3 CSV files · 70,443 total rows · 24 MB
- **Files:** `19drivers.csv` (8,261 rows), `4drivers.csv` (1,743 rows), `dailyRoutes.csv` (60,439 rows — primary file)
- **Format:** CSV with semicolon delimiter · 1 Hz
- **Confirmed columns (dailyRoutes — 33 cols):**

| Column | MisfireAI relevance |
|---|---|
| SHORT TERM FUEL TRIM BANK 1 | ✅ Core |
| SHORT TERM FUEL TRIM BANK 2 | ✅ Core |
| LONG TERM FUEL TRIM BANK 2 | ✅ Core — note: LTFT B1 absent (data gap) |
| ENGINE_COOLANT_TEMP | ✅ Core |
| ENGINE_RPM | ✅ Core |
| ENGINE_LOAD | ✅ Core |
| MAF | ✅ Core |
| INTAKE_MANIFOLD_PRESSURE | ✅ Core |
| AIR_INTAKE_TEMP | ✅ Core |
| AMBIENT_AIR_TEMP | ✅ Context |
| SPEED | ✅ Context |
| THROTTLE_POS | ✅ Context |
| TIMING_ADVANCE | ✅ Useful |
| FUEL_PRESSURE | ✅ Useful |
| TROUBLE_CODES | ✅ DTCs — 11,925 of 60,439 rows have codes populated |
| DTC_NUMBER | ✅ Count of active DTCs |
| EQUIV_RATIO | ✅ Useful |
| MARK / MODEL / CAR_YEAR | ✅ Vehicle metadata |
| LATITUDE / LONGITUDE / ALTITUDE | Context (GPS) |

- **STFT/LTFT:** ✅ STFT B1, STFT B2, LTFT B2 confirmed. ⚠️ LTFT B1 absent from dailyRoutes — present in other files as "Term Fuel Trim Bank 1"
- **O2 Sensors:** ❌ Not present
- **DTCs:** ✅ Real DTC codes in TROUBLE_CODES column — 11,925 rows populated (~20% of dataset). This is the only public dataset with real fault codes confirmed.
- **Mode 06:** ❌ Not present
- **Data quality notes:** Semicolon delimiter (not standard comma). Column naming inconsistent across files (spaces vs underscores, "Term" vs "Long Term"). ~21% of rows have no MARK/MODEL (blank). Brazilian vehicles — mostly European/Latin American market makes.
- **License:** Unknown — academic research, cite thesis
- **Verdict:** ✅ Most valuable public dataset found. Multi-make, multi-year, real DTCs, fuel trims across both banks, 60k+ rows. The DTC population is unique — no other public dataset has this. Key gap: no O2 sensors, LTFT B1 inconsistently named.

---

### 3. OBD-II & CAN-Based Driving Behavior Dataset ✅ DOWNLOADED & INSPECTED
- **Source:** Kaggle — Isay Gerard Ozamora
- **URL:** https://www.kaggle.com/datasets/isaygerardozamora/obd-ii-and-can-based-driving-behavior-dataset
- **Local path:** `data/external/isay-gerard-obd/`
- **Vehicle:** KIA Soul (1 vehicle, 10 drivers — 3 per-driver files + 1 combined classified file)
- **Size:** 4 CSV files · ~1,110,000 rows total · 139 MB
  - `Data_Driver1.csv` — 174,600 rows · 33 cols
  - `Data_Driver2.csv` — 183,600 rows · 33 cols
  - `Data_Driver3.csv` — 196,800 rows · 33 cols
  - `OBD-II Driving Data - Classified.csv` — 555,000 rows · 35 cols (includes `Label` and `Conductor_ID`)
- **Format:** CSV · Spanish-language column headers (UTF-8, some encoding artifacts) · 1 Hz
- **Note on column names:** Headers are in Spanish with units embedded (e.g. `Ajuste de combustible a corto plazo (Banco 1) [%]`). Must map to English PID names on ingest.
- **Confirmed columns (33–35 cols):**

| Column (translated) | MisfireAI relevance |
|---|---|
| STFT B1 (Ajuste corto plazo Banco 1) | ✅ Core — range: -7.0% to +12.5%, mean +0.48%, stdev 1.88 |
| LTFT B1 (Ajuste largo plazo Banco 1) | ✅ Core — range: -0.8% to +4.7%, mean +0.37%, stdev 1.15 |
| LTFT secondary lambda B1 | ✅ Useful — secondary O2 long-term correction |
| Engine RPM | ✅ Core |
| Engine Load | ✅ Core |
| Coolant Temp (°C) | ✅ Core |
| MAP (kPa) | ✅ Core (MAP-based engine) |
| Intake Air Temp (°C) | ✅ Core |
| Timing Advance (°) | ✅ Core — range: -14.5° to +39.5°, mean 12.25°, stdev 11.74 |
| Vehicle Speed (km/h) | ✅ Context |
| Throttle Position (abs + relative + B + pedal D/E) | ✅ Context — 5 throttle columns |
| Catalyst Temp B1 S1 (°C) | ✅ Core — range: 490–876°C, mean 674°C |
| O₂ sensor equivalence ratio B1 S1 | ✅ Core — wideband lambda sensor |
| O₂ sensor current B1 S1 (mA) | ✅ Core — wideband current output |
| Lambda sensor voltage B1 S2 | ✅ Downstream O2 (narrowband voltage) |
| Commanded A/F equivalence ratio | ✅ Useful |
| Evaporative purge commanded (%) | ✅ Useful — EVAP system |
| Barometric pressure (kPa) | ✅ Context |
| Battery voltage | ✅ Context |
| Fuel level (%) | Context |
| MIL distance traveled (km) | ✅ DTC indicator |
| Distance since codes cleared (km) | ✅ DTC indicator |
| Warm-ups since codes cleared | ⚠️ Always 255 — rollover artifact (same as carOBD) |
| Steering wheel angle + speed | Context (CAN bus signals) |
| **Label** (classified file only) | ✅ Driving behavior class — 0: aggressive (118,398 rows), 1: normal (436,602 rows) |
| **Conductor_ID** (classified file only) | ✅ Driver identifier |

- **STFT/LTFT:** ✅ STFT B1 + LTFT B1 confirmed with ranges. ⚠️ Single bank only (KIA Soul is single-bank). No STFT/LTFT B2.
- **O2 Sensors:** ✅ Both wideband (equivalence ratio + current, upstream) and narrowband voltage (downstream) present — most complete O2 coverage of any public dataset found.
- **Catalyst Temp:** ✅ Confirmed with real values (490–876°C range)
- **Timing Advance:** ✅ Full range including negative values (knock retard visible in data)
- **DTCs:** ⚠️ MIL distance present but no actual DTC codes column
- **Mode 06:** ❌ Not present
- **Driving behavior labels:** ✅ Unique — aggressive vs. normal driving classified. Timing advance and catalyst temp will differ between classes — useful for teaching the model what "hard driving" looks like vs. fault signatures.
- **License:** Springer Nature / PMC Open Access — cite academic paper
- **Verdict:** ✅ Best overall dataset for MisfireAI. 1.1M rows, O2 sensors present (unique), catalyst temp, timing advance with knock retard, labeled driving behavior. Single-bank KIA Soul limits it to B1 trims only. The O2 and catalyst temp columns make fault correlation scenarios possible that aren't in carOBD or cephasax.

---

## Tier 2 — Potentially Useful (Real OBD2, Fuel Trim Status Unconfirmed)

---

### 3. Levin Vehicle Telematics ⚠️ INSPECTED — STFT/LTFT ABSENT
- **Source:** Kaggle + GitHub — YunSolutions
- **Kaggle:** https://www.kaggle.com/datasets/yunlevin/levin-vehicle-telematics
- **GitHub:** https://github.com/YunSolutions/levin-openData
- **Local path:** `data/external/levin-openData/` (README + DataDescription only — actual data behind external links)
- **Vehicles:** ~30 vehicles, 4-month collection
- **Format:** CSV, SQLite3, ZIP · OBD @ 1 Hz, accelerometer @ 25 Hz
- **Confirmed PIDs (from DataDescription):** cTemp (coolant), dtc (fault count integer), eLoad, iat (intake air temp), imap (MAP), maf, rpm, speed, tAdv (timing advance), tPos (throttle position)
- **STFT/LTFT:** ❌ Not present — confirmed absent from DataDescription column list
- **O2 Sensors:** ❌ Not present
- **DTCs:** ⚠️ `dtc` column is a count integer (number of active faults) — not actual DTC codes
- **Mode 06:** ❌ Not present
- **License:** Creative Commons BY-NC-SA (non-commercial only)
- **Notes:** Actual data files not in GitHub repo — behind mega.nz / Google Drive links requiring authentication. Only README and DataDescription confirmed downloaded. LEVIN proprietary OBD dongle likely explains the narrow PID set. Without STFT/LTFT, value to MisfireAI is limited.
- **Verdict:** ❌ Downgraded. Fuel trims absent. DTC count but no codes. Multi-vehicle diversity is the only remaining value — not worth pursuing further unless column list is revised.

---

### 4. Driving Datasets OBD-II/CAN-BUS ❌ INSPECTED — TOO SMALL, POOR STRUCTURE
- **Source:** Kaggle — Anwar Mehmood Sohail (University of Malaya)
- **URL:** https://www.kaggle.com/datasets/anwarmehmoodsohail/driving-datasets-obd-iican-bus
- **Local path:** `data/external/anwar-mehmood-obd/`
- **Vehicles:** 1–2 vehicles (single VIN "Sohail"), Pakistan (Peshawar/UET route data)
- **Size:** 19 CSV files · ~374 usable OBD rows total · 632 KB
- **Format:** Mixed — most files are GPS route coordinates only (lat/lng/name). OBD data is embedded as JSON strings inside a `readings (M)` column (DynamoDB export format). Values include units in the string (e.g. `"-22.7%"`, `"85C"`) — requires parsing and stripping.
- **STFT/LTFT:** ✅ Present in 372/374 rows — but only B1 (single-bank vehicle). B2 always NODATA.
- **O2 Sensors:** ❌ Not present
- **DTCs:** ✅ TROUBLE_CODES present in 94 rows (e.g. P2122) — but only in 1 of 3 OBD files
- **Mode 06:** ❌ Not present
- **License:** Unknown
- **Data quality:** Most files are GPS-only with no OBD signals. LTFT B1 at -22.7% in one file suggests the vehicle had an active rich condition — but with only 374 rows total this is anecdotal. JSON-in-CSV format requires custom parsing. Many columns unnamed or blank.
- **Verdict:** ❌ Not useful. 374 rows is not enough for any meaningful analysis. Format is messy (JSON embedded in CSV, values with units as strings). Skip.

---

### 5. OBD Dataset ❌ UNAVAILABLE
- **Source:** Kaggle — dommatap
- **URL:** https://www.kaggle.com/datasets/dommatap/obd-dataset
- **Status:** Dataset deleted or made private. URL returns 404 as of May 2026. Cannot be downloaded.
- **Verdict:** Skip.

---

### 6. cephasax OBD-II Datasets — *see Tier 1, entry #2*
- **Source:** Kaggle + GitHub — cephasax (UFRN master's research)
- **Kaggle:** https://www.kaggle.com/datasets/cephasax/obdii-ds3
- **Note:** This is the same dataset as Tier 1 entry #2. Fully inspected and confirmed — STFT B1/B2, LTFT B2, real DTC codes in 11,925 rows. Moved to Tier 1.

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

### 9. telemetry-obd Logger + Data ⚠️ INSPECTED — NO PUBLIC SAMPLE DATA IN REPO
- **Source:** GitHub — thatlarrypearson
- **URL:** https://github.com/thatlarrypearson/telemetry-obd
- **Vehicles:** Multiple (organized by VIN, Raspberry Pi-based collection)
- **Format:** Line-delimited JSON (one record per sample, ISO-8601 timestamps)
- **STFT/LTFT:** ✅ Config includes `SHORT_FUEL_TRIM_1`, `SHORT_FUEL_TRIM_2`, `LONG_FUEL_TRIM_1`, `LONG_FUEL_TRIM_2` — tool *can* collect them, but no downloadable sample dataset in repo
- **O2 Sensors:** ✅ Config also includes `SHORT_O2_TRIM_B1/B2`, `LONG_O2_TRIM_B1/B2` — same caveat
- **DTCs:** Config-dependent
- **Mode 06:** Config-dependent
- **License:** MIT
- **Notes:** Primarily a Raspberry Pi logging tool. The README references a Ford F-450 inline example but no actual data files are in the GitHub repo. JSON format with per-record timestamps maps well to MisfireAI's normalized schema — could be a useful **ingest format reference** even without sample data. Tool is actively maintained (last push May 2025).
- **Verdict:** ❌ No sample data to download. Useful as ingest format reference and as a tool that could generate live data. Not a public dataset source.

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

## Mode 06 — Gap and Plan

**Mode 06 data is absent from every public dataset.** Mode 06 (On-Board Monitor Test Results) provides the raw measured value plus min/max thresholds for on-board monitors — catalyst efficiency, O2 sensor response, EGR flow, etc. A standard scanner says pass/fail. Mode 06 says how far from the threshold you actually are.

MisfireAI does **not** depend on Mode 06 for predictive scoring. The primary scoring methods are fuel trim trending and statistical baseline deviation — both work on Mode 01 data from any hardware. Mode 06 is a **third scoring method** that enhances prediction when available.

**Mode 06 research plan:**
- Test Zurich BT1 + Car Scanner / OBD Fusion for Mode 06 capability on multiple vehicles
- Confirm whether Dragy exposes Mode 06 when it arrives
- Investigate FORScan (Ford/Mazda), Techstream (Toyota), ISTA (BMW) for Mode 06 exports
- ESP32 + raw CAN is the likely path to reliable Mode 06 at scale — bypasses ELM327 limitations
- If a third-party app on the Zurich BT1 can pull Mode 06, that's the lowest-effort path

The only sources for Mode 06 data today are live capture via compatible hardware or proprietary scan tool exports. Once any path is confirmed working, it becomes an optional enrichment layer that upgrades scoring quality without being a dependency.

---

## Priority Download List

Status as of May 2026:

1. **carOBD (GitHub)** — ✅ Downloaded & inspected. `data/external/carOBD/`
2. **cephasax OBD-II (GitHub)** — ✅ Downloaded & inspected. `data/external/cephasax-OBDdatasets/`
3. **Isay Gerard OBD-II & CAN (Kaggle)** — ✅ Downloaded & inspected. `data/external/isay-gerard-obd/` — 1.1M rows, O2 sensors, catalyst temp, timing advance, labeled driving behavior.
4. **telemetry-obd sample data (GitHub)** — ⏳ Not yet pulled. JSON format multi-vehicle. Low friction download.
5. **Levin Vehicle Telematics** — ❌ Deprioritized. STFT/LTFT absent. Actual data behind authentication-gated external links.
6. **Anwar Mehmood (Kaggle)** — ❌ Inspected. 374 rows total, JSON-in-CSV format, not usable.
7. **dommatap (Kaggle)** — ❌ 403 Forbidden. Dataset access restricted — cannot download.

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
