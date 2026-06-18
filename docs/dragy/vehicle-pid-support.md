---
date: 2026-06-17
status: open
unit: U5
origin: docs/plans/2026-06-17-001-feat-dragy-deep-data-acquisition-plan.md
---

# U5: Manufacturer PID Reachability — Owned Vehicles

**Goal:** Establish which enhanced/manufacturer PIDs the owned vehicles actually expose, and over what protocol/addressing — the precondition for any deep capture (Dragy or ESP32).

**Verification target:** Per-vehicle table of U1 target PIDs with respond/no-respond, protocol, and mode.

---

## Vehicle(s) Tested

| Vehicle | VIN | ECU | OBD Protocol |
|---------|-----|-----|--------------|
| BMW 335i (N54 engine) | — | MSD80/MSD81 | ISO 15765-4 CAN |
| _[ other vehicles ]_ | | | |

---

## Probe Tool

_[ to be filled in ]_

- Tool used: (e.g., OBD Fusion, BimmerCode, custom ELM327 script)
- Adapter: (e.g., ELM327 BT, bimmerlink dongle)
- Protocol access: generic Mode 01 only / manufacturer modes / raw CAN

---

## BMW N54 PID Support

Target PIDs from `docs/dragy/pid-target-set.md`:

### Must-Have Deep PIDs

| Canonical Name | OBD Mode / PID | Responds? | Protocol | Notes |
|---|---|---|---|---|
| STFT_B1 | Mode 01 / 0x06 | — | — | Generic, should be reachable |
| STFT_B2 | Mode 01 / 0x07 | — | — | Generic |
| LTFT_B1 | Mode 01 / 0x08 | — | — | Generic |
| LTFT_B2 | Mode 01 / 0x09 | — | — | Generic |
| TIMING_CYL1–6 (knock) | BMW manufacturer | — | — | Enhanced PID, requires manufacturer mode |
| KNOCK_RETARD | Derived from CYL1-6 | N/A | N/A | Derived, not a direct PID |

### Nice-to-Have PIDs

| Canonical Name | OBD Mode / PID | Responds? | Protocol | Notes |
|---|---|---|---|---|
| CAT_TEMP_B1S1 | Mode 01 / 0x3C | — | — | Generic |
| O2_VOLT_B1S2 | Mode 01 / 0x15 | — | — | Generic |

---

## Findings

_[ to be filled in after probing ]_

**Generic Mode 01 coverage:** _[ list what responds ]_

**Manufacturer/enhanced PID access:** _[ what tool/method was required, what responded ]_

**Protocol used by Dragy for PID requests:** _[ generic Mode 01 only / enhanced / unknown ]_

---

## Conclusion

_[ to be filled in ]_

Does the bus level expose the deep PIDs (knock/trims) at all?  
**Yes / No / Partial**

What does Dragy's BLE stack need to reach them?  
_[ generic ELM327-style / manufacturer PID extension / raw CAN ]_
