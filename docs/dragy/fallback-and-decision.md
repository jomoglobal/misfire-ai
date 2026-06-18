---
date: 2026-06-17
status: open
unit: U6
origin: docs/plans/2026-06-17-001-feat-dragy-deep-data-acquisition-plan.md
---

# U6: ESP32 + CAN Fallback and Go/No-Go Framework

**Goal:** Document the fallback path and the explicit decision framework that triggers it. The investigation ends in a decisive outcome, not a stall.

---

## Why Raw CAN Beats App-Mediated OBD2

Generic OBD2 (Mode 01) over BLE is constrained by the app's PID selection. Dragy curates a track-performance set that excludes diagnostic signals (fuel trims, per-cylinder timing/knock). The physical CAN bus on the vehicle carries all of these signals — the limitation is the software layer, not the hardware.

Raw CAN access bypasses the OBD2 framing layer entirely:
- **No PID whitelist** — reads any ECU broadcast frame at any cycle rate
- **No 10 Hz cap** — CAN buses run at 500 kbps (most modern vehicles); diagnostic frames broadcast at 10–100 Hz natively
- **Manufacturer PIDs reachable** — BMW knock/per-cylinder timing are accessible via manufacturer-specific CAN messages not exposed by generic Mode 01

The tradeoff: requires physical hardware tapped into the OBD2 port, and protocol decoding for manufacturer frames requires reverse-engineering or manufacturer-supplied DBC files.

---

## ESP32 + CAN Transceiver Approach (Directional)

This is NOT a build specification — it is a directional sketch for the fallback if Dragy proves unreachable.

**Hardware components:**
- ESP32 microcontroller (~$5–10): WiFi+BT for data offload, sufficient compute for CAN frame processing
- CAN transceiver (MCP2515 or TJA1050, ~$3–8): hardware layer between ESP32 and OBD2 port
- OBD2 connector / breakout (~$5): physical access to CAN H/L lines

**Data flow:**
1. ESP32 + transceiver tap OBD2 port CAN bus
2. Log all frames to SD card or stream over WiFi
3. Filter/decode frames using DBC or reverse-engineered PID addresses (from U5)
4. Export as CSV / structured format → feed into MisfireAI VBO adapter or a new `esp32` source

**CAN addressing for BMW N54:**
- Standard CAN ID range for diagnostic responses: varies; requires U5 findings
- Known: BMW manufacturer PIDs require extended addressing (ISO 15765-2 functional addressing with target address 0x6F1 / 0x12)

**Cost estimate:** $15–25 in parts for a one-off unit; sub-$10 at volume.

---

## Go/No-Go Decision Framework

The threshold value is intentionally left for the user to set once U3–U5 milestones report. This section provides the milestone checklist.

### Milestone Checklist

| Milestone | Unit | Status | Finding |
|-----------|------|--------|---------|
| Dragy BLE reachable / driveable | U3 | open | — |
| Diagnostic PID observed in BLE stream | U3 | open | — |
| Vendor replied with useful protocol info | U4 | open | — |
| Beta app exposes additional diagnostic PIDs | U4 | open | — |
| Owned vehicles expose deep PIDs at bus level | U5 | open | — |
| Deep PID capture achieved via Dragy | U3+U4 | open | — |

### Decision Matrix

_[ user fills in thresholds after first attempts ]_

| Condition | Action |
|-----------|--------|
| Dragy BLE reachable AND diagnostic PIDs observable | Continue with Dragy; implement custom BLE driver |
| Dragy BLE authenticated/obfuscated AND vendor unresponsive AND deep PIDs exist at bus (U5 confirms) | Trigger ESP32 fallback |
| Deep PIDs NOT present at bus level at all (U5 finds none) | Investigate different vehicle / alternative approach |
| _[ user-defined threshold ]_ | _[ action ]_ |

---

## Outstanding: Go/No-Go Threshold

The user has explicitly left the go/no-go exit criterion undefined until first attempts reveal Dragy's reachability (see origin Outstanding Questions). This section is the placeholder that converts those milestones into a decision once U3–U5 complete.

**To complete this document:** After U3, U4, U5 report findings, return here and fill in the threshold row in the Decision Matrix.
