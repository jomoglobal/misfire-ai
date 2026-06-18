---
date: 2026-06-17
topic: dragy-deep-data-acquisition
---

# Deep + High-Frequency Data Acquisition via Dragy OBD

## Summary

A bounded investigation to get **deep, high-frequency** vehicle data — the diagnostic PIDs that make MisfireAI's analysis meaningful (fuel trims, per-cylinder timing/knock, catalyst/exhaust temp) at high sample rate — out of the **Dragy OBD adapter already owned**, by reverse-engineering its BLE protocol and pushing Dragy's team for custom-PID access. A self-built raw-CAN logger (ESP32 + CAN transceiver) is the documented fallback if Dragy proves to be a sealed black box. The go/no-go exit criterion is intentionally left open until first attempts reveal how reachable Dragy actually is.

---

## Problem Frame

MisfireAI's differentiator is depth: longitudinal analysis of signals like fuel trim drift and knock retard that most tools never read (see `signal-decision.md`, `docs/brainstorms/2026-06-12-obd2-signal-interpretation.md`). The 484-session demo dataset was captured with **MHD**, which is BMW-only — so the current deep-analysis capability does not generalize to other vehicles.

The Dragy OBD adapter was acquired as the candidate "universal" logger. Inspection of a real captured session (`data/sample/dragylap_20260606_162501_HF Perris to Home.vbo`, 14,952 rows over ~25 min) shows what its app actually delivers:

- **Steady 10 Hz**, GPS + motion channels, and only **~8 generic OBD2 channels**: rpm, speed, coolant_temp, intake_temp, manifold_flow (MAF), throttle_pos, engine_load, timing_advance.
- **None** of the diagnostic depth: no fuel trims, no per-cylinder timing (so no KNOCK_RETARD), no catalyst/O2.
- The app only records in **fixed lap/drag modes**, not open-ended driving — a workflow dead-end for accumulating arbitrary drive history.

This is the specific pain: the generic-PID set Dragy's app produces is **no better than the existing ELM327 + Car Scanner setup already on hand**. It adds nothing MisfireAI doesn't already have. Meanwhile the *hardware* is capable of far more — Dragy markets the OBD adapter as 200 Hz, CAN-bus, with custom-PID support — but that capability is locked inside Dragy's own apps, which curate a track-performance PID set that excludes diagnostic signals. There is no API, no SDK, the saved `.dlap`/`.group` files are encrypted, and the only contact channel found is customer service (`orders@godragy.com`) plus a Facebook feedback thread. The deep+fast data physically exists on the device's CAN interface; today every path to it runs through software that doesn't expose what MisfireAI needs.

---

## Requirements

**Target data contract (what "worth building" means here)**
- R1. Define the **deep capture PID target set** MisfireAI needs beyond the generic baseline — at minimum: short/long-term fuel trims (per bank), per-cylinder timing correction (knock), catalyst/exhaust temp, and downstream O2 — with the generic baseline (rpm, load, throttle, MAF, coolant, timing) as mandatory companion channels for condition segmentation.
- R2. Any acquisition path is only acceptable if it delivers **more PIDs than generic OBD2 Mode 01** AND at a sample rate at least matching the current 10 Hz. Standard-BLE-only capture (generic Mode 01) is explicitly rejected as it equals the existing ELM327 capability.
- R3. Captured output must land in MisfireAI's existing canonical schema (the `SOURCE_COLUMN_MAP` / `detect_source` normalization layer in `tools/mcp_server.py` and `tools/schema.py`), so a new source format is added the same way MHD/CarScanner already are — not a separate pipeline. Verify the current mapping layer supports adding a `dragy` source before relying on this.

**Dragy investigation (primary track)**
- R4. Join the Dragy OBD beta apps (TestFlight / Google Play links in the 2026-05-08 "Dragy OBD – Updated app version & feedback thread" email) and the linked Facebook feedback threads, to access the latest custom-PID and recording capabilities and the only available support channel.
- R5. Capture and analyze the **Dragy BLE traffic** during a logging session to determine whether the high-speed custom-PID stream can be driven outside Dragy's app, and whether diagnostic PIDs can be requested over it.
- R6. Make a **direct technical ask** to Dragy (via `orders@godragy.com` / feedback thread / any developer channel they name) specifically about: (a) adding diagnostic PIDs — fuel trim, per-cylinder timing — to the logged set, (b) open-ended (non-lap) recording, and (c) BLE protocol or developer documentation.
- R7. Determine, for the specific vehicles on hand, which **manufacturer/enhanced PIDs** (e.g., BMW knock/trims) are reachable over whatever protocol Dragy uses — generic OBD2 modes alone will not surface them.

**Fallback path (documented, not built yet)**
- R8. Record the **ESP32 + CAN transceiver** raw-CAN logger as the committed fallback if the Dragy investigation hits a confirmed wall, including why raw CAN can reach deep PIDs at high frequency that app-mediated OBD2 cannot. Building it is out of scope for this effort (see Scope Boundaries).

---

## Success Criteria

- **Decisive answer, not a stall:** at the end of the effort it is clearly known whether Dragy can deliver deep + high-frequency diagnostic PIDs on the owned vehicles — yes (with a documented capture method) or no (wall identified, reason recorded, fallback triggered).
- **Real proof when yes:** at least one captured session containing one or more *deep* PIDs (a fuel trim or per-cylinder timing value) at ≥10 Hz, normalized into MisfireAI's canonical schema and ingested by the existing pipeline.
- **Clean handoff:** a planner picking this up knows the target PID set (R1), the rejected path and why (standard BLE), the investigation steps and their outcomes, and the exact condition under which to switch to ESP32 — without re-deriving the Dragy capability analysis done here.

---

## Scope Boundaries

- **In:** Dragy BLE protocol investigation; beta-app + feedback-thread participation; a direct technical ask to Dragy; defining the deep-capture PID target set; confirming the canonical schema can absorb a Dragy source; determining manufacturer-PID reachability on the owned cars.
- **Deferred for later:** building the ESP32 + CAN logger (fallback only, if Dragy fails); the eventual sub-$25 replicable hardware product; rollout to vehicles beyond the ones physically on hand; multi-vehicle "any car" generalization.
- **Rejected (not a deferral):** a standard-BLE-only custom logger — it delivers nothing beyond the existing ELM327 + Car Scanner setup; reverse-engineering the encrypted stored `.dlap`/`.group` files — the live BLE stream is the better target than decrypting saved output.

---

## Key Decisions

- **Crack Dragy first, before building hardware:** the adapter is already owned, demonstrably captures clean 10 Hz data, and (if its BLE is reachable) yields a 200 Hz custom-PID engine at near-zero added hardware cost. ESP32 is the fallback, not the opening move.
- **Depth + speed is the bar, not universality-for-its-own-sake:** an acquisition path that doesn't beat generic Mode 01 is not worth building, even if it works on more cars. Confirmed directly by the user against the standard-BLE option.
- **Two parallel tracks:** active BLE/technical investigation (primary) plus a low-effort push on Dragy's team (upside), with no dependency on Dragy's responsiveness for the primary track to progress.

---

## Dependencies / Assumptions

- **No Dragy developer program exists today.** Confirmed via 6-month email review: no API/SDK, no reply to the prior developer request, support is customer-service + Facebook only. Approach B's payoff depends on a third party with no visible developer channel — pursued as upside, not relied upon.
- **Assumption (unverified):** Dragy's high-speed custom-PID mode can be made to log *diagnostic* PIDs (trims, knock), not only the track-performance set it ships with. This may be false — the app may be hard-limited to performance channels.
- **Assumption (unverified):** Dragy's BLE protocol is reachable/replayable. As a beta product it may use authenticated or obfuscated BLE that resists sniffing.
- **Assumption (unverified):** the owned vehicles expose the desired manufacturer PIDs over the protocol Dragy uses. Generic OBD2 modes will not surface BMW-specific knock/trim data.
- The `.dlap` file is a ZIP containing a map PNG + an encrypted `.group` telemetry blob; the `.vbo` export is the only human-readable Dragy output and is the ground truth for what the app currently logs.

---

## Outstanding Questions

### Resolve Before Planning

- [Affects R4–R8][User decision] What bounds the Dragy investigation before committing to the ESP32 fallback? Deliberately left undefined for now — to be set after the first attempts (BLE sniff, beta participation, first Dragy reply, first deep-PID capture) reveal how reachable Dragy is. Planning should treat these as the milestones that inform the go/no-go, with the threshold chosen once they are underway.

### Deferred to Planning

- [Affects R5][Needs research] What tooling captures Dragy's BLE traffic (e.g., phone BLE HCI snoop log, nRF Sniffer) and how is the custom-PID stream distinguished from standard OBD2 requests?
- [Affects R7][Needs research] Which manufacturer PID sets do the owned vehicles expose, and over what protocol/addressing does Dragy issue requests?
- [Affects R3][Technical] Exact column names and units Dragy emits (from the `.vbo` header) and how they map to canonical names — straightforward once a capture method is fixed.
- [Affects R8][Needs research] Concrete ESP32 + CAN hardware/firmware path (transceiver choice, CAN bitrate detection, BMW PID addressing) — only if the fallback is triggered.
