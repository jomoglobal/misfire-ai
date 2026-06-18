---
date: 2026-06-17
status: open
unit: U3
origin: docs/plans/2026-06-17-001-feat-dragy-deep-data-acquisition-plan.md
---

# U3: Dragy BLE Traffic Investigation

**Goal:** Determine empirically whether Dragy's high-speed/custom-PID stream can be observed and driven outside the Dragy app, and whether diagnostic PIDs can be requested over it.

**Verification target:** A definitive "reachable / not reachable" conclusion with evidence.

---

## Tooling Used

_[ to be filled in during investigation ]_

- Capture method: Android BLE HCI snoop log / nRF Sniffer + dongle
- Device under test: Dragy OBD adapter (model: ...)
- App version during capture: ...
- Capture duration: ...

---

## GATT Profile

_[ to be filled in during investigation ]_

- Service UUID(s): ...
- Characteristic UUIDs: ...
- Notify vs Write characteristics: ...

---

## Protocol Analysis

_[ to be filled in during investigation ]_

- Standard OBD2 framing detected: yes / no
- Proprietary high-speed framing: yes / no / unknown
- Authentication / obfuscation observed: yes / no
- PID request format (if observable): ...

---

## Diagnostic PID Probe Results

_[ to be filled in during investigation ]_

Attempt to issue each of the following (from `docs/dragy/pid-target-set.md` must-have list) via the BLE connection:

| PID | Mode | Response | Notes |
|-----|------|----------|-------|
| STFT Bank 1 | Mode 01 / 0x01 PID 0x06 | — | |
| LTFT Bank 1 | Mode 01 / 0x01 PID 0x07 | — | |
| Per-cylinder timing (knock) | Manufacturer / enhanced | — | BMW-specific |

---

## Evidence Artifacts

_[ file paths or links to raw capture files ]_

---

## Conclusion

**Reachable / Not Reachable / Inconclusive**

_[ to be filled in ]_

Reason:
