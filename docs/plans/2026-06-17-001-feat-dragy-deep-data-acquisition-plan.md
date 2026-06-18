---
date: 2026-06-17
type: feat
status: active
origin: docs/brainstorms/2026-06-17-dragy-deep-data-acquisition-requirements.md
---

# feat: Dragy Deep + High-Frequency Data Acquisition Investigation

## Summary

An investigation plan to determine whether the owned Dragy OBD adapter can deliver deep, high-frequency diagnostic PIDs (fuel trims, per-cylinder timing/knock, catalyst/exhaust temp) beyond the ~8 generic channels its app exports today. The work is structured as research/spike units (BLE traffic capture, beta-app participation, a direct technical ask to Dragy, manufacturer-PID probing) plus one concrete code unit — a Dragy VBO source adapter that wires today's 10 Hz export into MisfireAI's existing canonical pipeline. The ESP32 + raw-CAN fallback is documented but not built. The go/no-go exit to the fallback is structured as a decision point, not a fixed deadline.

---

## Problem Frame

MisfireAI's differentiator is analytical depth — longitudinal fuel-trim drift and knock-retard detection — built today on MHD data that is BMW-only and does not generalize. The Dragy OBD adapter was acquired as the candidate universal logger, but a real captured session (`data/sample/dragylap_20260606_162501_HF Perris to Home.vbo`) shows its app delivers only ~8 generic OBD2 channels at 10 Hz, with none of the diagnostic depth, and only in fixed lap/drag recording modes. That generic set is no better than the existing ELM327 + Car Scanner setup.

The Dragy hardware advertises 200 Hz, CAN-bus, and custom-PID support, but that capability is locked inside Dragy's apps, which curate a track-performance PID set excluding diagnostic signals. There is no API/SDK, the stored `.dlap`/`.group` files are encrypted, and the only contact channel is customer service plus a Facebook feedback thread (see origin: `docs/brainstorms/2026-06-17-dragy-deep-data-acquisition-requirements.md`). This plan resolves whether the deep data can be reached through the device the user already owns before committing to building separate hardware.

---

## Requirements Traceability

Carried from the origin requirements doc:

- **R1** — define the deep capture PID target set (fuel trims, per-cylinder timing/knock, cat/exhaust temp, downstream O2 + generic companion channels). → U1
- **R2** — any path must beat generic Mode 01 in PID count AND match ≥10 Hz; standard-BLE-only rejected. → U3, U5 (acceptance bar), Scope Boundaries
- **R3** — captured output lands in the existing canonical schema (`SOURCE_COLUMN_MAP` / `detect_source`), added like the other sources. → U2
- **R4** — join Dragy beta apps + feedback threads. → U4
- **R5** — capture and analyze Dragy BLE traffic. → U3
- **R6** — direct technical ask to Dragy (diagnostic PIDs, open recording, BLE/protocol docs). → U4
- **R7** — determine which manufacturer/enhanced PIDs are reachable on the owned vehicles. → U5
- **R8** — document the ESP32 + CAN fallback (not built). → U6

---

## Key Technical Decisions

- **Crack Dragy first, ESP32 is fallback** (see origin: Key Decisions). The adapter is owned, captures clean 10 Hz data, and would yield a 200 Hz custom-PID engine at near-zero hardware cost if its BLE is reachable. Building ESP32 is out of scope here.
- **VBO adapter is active work, not deferred.** Parsing the existing Dragy export into the canonical pipeline is low-risk, follows the established 5-source pattern, and makes the investigation's data legible immediately. This is distinct from the rejected "standard-BLE capture" path — it parses data already in hand rather than building a new shallow capture route.
- **VBO needs a section-aware parser path.** Dragy's `.vbo` is not comma-CSV: it has `[header]` / `[column names]` / `[data]` sections and space-delimited fixed-width rows. The existing CSV ingest path cannot parse it as-is; `ingest_file` needs a VBO-format branch before column mapping applies.
- **Go/no-go exit is a decision point, not a deadline** (see origin: Outstanding Questions). The plan structures the milestones that inform the decision; the threshold is chosen once first attempts reveal Dragy's reachability.
- **Spikes verify by captured artifact, not unit tests.** Only the VBO adapter (U2) is behavior-bearing code with test scenarios. Investigation units verify via concrete evidence (a sniffed packet log, a Dragy reply, a PID-support map).

---

## Implementation Units

### U1. Define the deep-capture PID target set

**Goal:** Produce the canonical "what we need logged" spec that every acquisition path is measured against — the acceptance bar for the whole investigation.

**Requirements:** R1, R2

**Dependencies:** none

**Files:**
- `docs/dragy/pid-target-set.md` (create) — the target PID spec
- `tools/schema.py` (reference only — align names to existing `SIGNAL_SCHEMA` canonical keys)

**Approach:** Enumerate the deep PIDs MisfireAI needs (STFT/LTFT per bank, per-cylinder timing → KNOCK_RETARD, CAT_TEMP_B1S1, downstream O2) and the mandatory generic companions for condition segmentation (RPM, LOAD_ABS, THROTTLE_POS, MAF, coolant, timing). Map each to its existing canonical name in `SIGNAL_SCHEMA` and note current source availability. Mark which are "must-have to beat ELM327" vs. "nice-to-have." This doc is the measuring stick referenced by U3, U4, U5.

**Patterns to follow:** `tools/schema.py` `SIGNAL_SCHEMA` canonical names and `source_availability` structure; depth rationale in `signal-decision.md` and `docs/brainstorms/2026-06-12-obd2-signal-interpretation.md`.

**Test scenarios:** Test expectation: none — documentation artifact, no behavioral change.

**Verification:** The doc lists every target PID with its canonical name, current availability, and must-have/nice-to-have tier; U3–U5 can reference it as the pass/fail bar.

---

### U2. Add Dragy VBO as a canonical pipeline source

**Goal:** Make the existing Dragy `.vbo` export ingest cleanly into the canonical pipeline, so current (and future deeper) Dragy data is legible to MisfireAI without a separate pipeline.

**Requirements:** R3 (and establishes the landing zone R2-qualifying data will use)

**Dependencies:** U1 (canonical name alignment)

**Files:**
- `tools/schema.py` (modify) — add `dragy` entries to `SIGNAL_SCHEMA` `source_availability`, add `(dragy, raw_col)` pairs to `SOURCE_COLUMN_MAP`, add any needed `UNIT_CONVERSIONS` (VBO velocity is km/h; coolant/intake units per header), extend `detect_source` with a Dragy branch
- `tools/mcp_server.py` (modify) — add a VBO-format parse path in/ahead of `ingest_file` that reads the `[column names]` line and `[data]` section from space-delimited rows
- `tools/test_dragy_ingest.py` (create) — tests for VBO detection, parsing, and mapping
- `data/sample/dragylap_20260606_162501_HF Perris to Home.vbo` (fixture, exists)

**Approach:** `.vbo` is section-structured and space-delimited, unlike the comma-CSV sources. Add a parser branch that extracts the column-names line and the `[data]` rows, then feeds the existing `_build_col_map` / canonical-mapping flow. Map Dragy's raw headers (`rpm-obd`, `coolant_temp-obd`, `intake_temp-obd`, `manifold_flow-obd`, `throttle_pos-obd`, `engine_load-obd`, `timing_advance-obd`, `speed-obd`, plus GPS/motion channels) to canonical names; GPS/motion channels have no canonical home today — map what fits, drop the rest explicitly (None in the col map) rather than inventing schema. Extend `detect_source` to recognize the VBO `[header]` marker or the `-obd` suffix convention.

**Patterns to follow:** the existing 5-source pattern in `tools/schema.py` (`SOURCE_COLUMN_MAP`, `detect_source`); `ingest_file` / `_build_col_map` in `tools/mcp_server.py`; how `mhd` handles a non-standard header (MHD version-string filtering) as precedent for format-specific pre-processing.

**Test scenarios:**
- `detect_source` returns `dragy` for the VBO sample's column set, and does not misclassify it as another source.
- Parsing the `[data]` section yields the correct row count (14,952 for the sample fixture) with numeric values, ignoring the `[header]`/`[comments]`/`[column units]` sections.
- Each mapped Dragy raw header resolves to its expected canonical name; unmapped GPS/motion columns are explicitly skipped, not silently misassigned.
- Unit conversion applies where declared (e.g., velocity km/h handling) and leaves already-canonical-unit channels untouched.
- A malformed/short trailing row (the sample has one) is handled without aborting the whole parse — partial last row is skipped, prior rows preserved.
- Ingesting the sample produces a normalized snapshot the existing pipeline accepts (no "No recognizable OBD2 columns" error).

**Verification:** `ingest_file` on the sample `.vbo` returns a normalized snapshot with `source: dragy` and the expected canonical columns populated; the new tests pass.

---

### U3. Capture and analyze Dragy BLE traffic

**Goal:** Determine empirically whether Dragy's high-speed/custom-PID stream can be observed and driven outside the Dragy app, and whether diagnostic PIDs can be requested over it.

**Requirements:** R5, R2 (informs whether a deep+fast path exists)

**Dependencies:** U1 (knows which PIDs to look for)

**Files:**
- `docs/dragy/ble-investigation.md` (create) — tooling used, capture method, findings, raw evidence pointers

**Approach:** Capture BLE traffic during a Dragy logging session (Android BLE HCI snoop log is the lowest-friction option; nRF Sniffer + dongle is the higher-fidelity option). Identify the GATT service/characteristics Dragy uses, distinguish standard OBD2 request/response framing from any proprietary high-speed framing, and determine whether issuing a request for a diagnostic PID (e.g., a fuel-trim Mode 01 PID, or a manufacturer PID identified in U5) returns data. Record whether the stream is authenticated/obfuscated (a plausible beta-product blocker per origin assumptions).

**Test scenarios:** Test expectation: none — investigation spike; verification is by captured artifact.

**Verification:** The doc states, with evidence: (a) what BLE service/characteristics Dragy uses, (b) whether the traffic is replayable/driveable externally or is authenticated/obfuscated, (c) whether any diagnostic PID was successfully requested. A definitive "reachable / not reachable" conclusion is recorded.

---

### U4. Join Dragy beta + make the direct technical ask

**Goal:** Exhaust the low-effort upside path — latest beta capabilities and a direct, specific request to Dragy's team — in parallel with the technical investigation.

**Requirements:** R4, R6

**Dependencies:** U1 (so the ask names the exact PIDs needed)

**Files:**
- `docs/dragy/vendor-contact.md` (create) — the sent ask, beta versions joined, and any response

**Approach:** Join the OBD beta apps (TestFlight / Google Play links in the 2026-05-08 "Dragy OBD – Updated app version & feedback thread" email) and the linked Facebook feedback threads. Send a direct technical ask to `orders@godragy.com` / the feedback thread covering: (a) adding diagnostic PIDs — fuel trim, per-cylinder timing — to the logged set, (b) open-ended (non-lap) recording, (c) BLE protocol or developer documentation. Log versions installed and whether the newer beta exposes custom diagnostic PIDs or open recording that the analyzed `.vbo` lacked.

**Test scenarios:** Test expectation: none — vendor-interaction spike; no code.

**Verification:** The ask is sent and recorded verbatim; beta apps are installed with versions noted; any change in available PIDs / recording modes vs. the current `.vbo` is documented. (A vendor *reply* is not required to complete the unit — non-response within the chosen window is itself a recorded outcome.)

---

### U5. Probe manufacturer-PID reachability on the owned vehicles

**Goal:** Establish which enhanced/manufacturer PIDs (e.g., BMW knock/per-cylinder timing, trims) the owned vehicles actually expose, and over what protocol/addressing — the precondition for any deep capture, Dragy or ESP32.

**Requirements:** R7, R2

**Dependencies:** U1

**Files:**
- `docs/dragy/vehicle-pid-support.md` (create) — per-vehicle PID support map

**Approach:** Using an OBD2 query tool that supports manufacturer modes, enumerate which target PIDs from U1 each owned vehicle answers, distinguishing generic Mode 01 from manufacturer/enhanced PIDs and noting protocol (CAN vs. other) and addressing. This answers the origin assumption "the owned vehicles expose the desired manufacturer PIDs" with evidence and feeds both the Dragy verdict (U3) and the fallback design (U6).

**Test scenarios:** Test expectation: none — investigation spike; verification by captured artifact.

**Verification:** A per-vehicle table records, for each U1 target PID, whether it responds, via generic or manufacturer mode, and over which protocol — confirming or refuting that the deep PIDs are reachable at the bus level at all.

---

### U6. Document the ESP32 + CAN fallback and the go/no-go decision

**Goal:** Capture the fallback path and the explicit decision framework that triggers it, so the investigation ends in a decisive, documented outcome rather than a stall.

**Requirements:** R8, Success Criteria ("decisive answer, not a stall")

**Dependencies:** U3, U5 (their findings feed the decision and the fallback's PID-addressing design)

**Files:**
- `docs/dragy/fallback-and-decision.md` (create) — ESP32+CAN approach rationale and the go/no-go criteria

**Approach:** Document why raw CAN reaches deep PIDs at high frequency that app-mediated OBD2 cannot, and sketch the ESP32 + CAN-transceiver path at a directional level (transceiver class, CAN bitrate detection, manufacturer PID addressing informed by U5) — explicitly NOT a build. Capture the go/no-go decision as a checklist of the investigation milestones (BLE reachability from U3, vendor response from U4, manufacturer-PID reachability from U5, any deep-PID capture achieved) with the threshold left for the user to set once those milestones report in.

**Test scenarios:** Test expectation: none — documentation artifact.

**Verification:** The doc states the fallback rationale, a directional ESP32 approach, and a milestone-based go/no-go framework the user can apply to decide "continue with Dragy" vs. "switch to ESP32" — with no fixed deadline invented.

---

## System-Wide Impact

- **Pipeline ingest:** U2 adds a sixth source to `tools/schema.py` and a VBO parse path to `tools/mcp_server.py`. Low blast radius — additive, following the existing source pattern; risk is mis-detection of the new format vs. existing ones (covered by a U2 test scenario).
- **No changes** to scoring, analysis, the demo app, or the persistence layer. The deep-PID analysis logic already exists (it ran on MHD data); this work is about *feeding* it from a new source, not changing it.

---

## Scope Boundaries

### In scope
- Defining the deep-capture PID target set (U1)
- Dragy VBO source adapter into the canonical pipeline (U2)
- Dragy BLE investigation (U3), beta + vendor ask (U4), manufacturer-PID probing (U5)
- Documenting the ESP32 fallback and go/no-go framework (U6)

### Deferred for later
- Building the ESP32 + CAN logger (fallback only, if Dragy fails) — U6 documents, does not build
- The eventual sub-$25 replicable hardware product
- Rollout to vehicles beyond those physically on hand; multi-vehicle "any car" generalization

### Rejected (not a deferral)
- A standard-BLE-only custom capture path — delivers nothing beyond the existing ELM327 + Car Scanner setup (note: U2 parsing the existing export is distinct and *is* in scope)
- Reverse-engineering the encrypted stored `.dlap`/`.group` files — the live BLE stream (U3) is the better target than decrypting saved output

---

## Dependencies / Assumptions

- **No Dragy developer program exists today** (confirmed via origin email review). U4's payoff depends on a vendor with no visible developer channel — pursued as upside, not relied upon.
- **Unverified:** Dragy's high-speed mode can log *diagnostic* PIDs, not only track-performance channels (tested by U3/U4).
- **Unverified:** Dragy's BLE is reachable/replayable vs. authenticated/obfuscated (tested by U3).
- **Unverified:** the owned vehicles expose the desired manufacturer PIDs (tested by U5).
- Tooling for U3 (BLE sniffing) and U5 (manufacturer-PID query) must be available; if not, those units note the tooling gap as their outcome rather than silently stalling.

---

## Deferred to Implementation

- Exact BLE capture tooling choice (HCI snoop log vs. nRF Sniffer) — settled when U3 starts, based on what hardware is on hand.
- Exact Dragy raw-header → canonical-name mappings and unit conversions — finalized against the `.vbo` header when U2 is implemented.
- The go/no-go threshold value — explicitly left for the user to set once U3–U5 milestones report (per origin Outstanding Questions).
- ESP32 transceiver/firmware specifics — only if the fallback is triggered.

---

## Suggested Sequencing

U1 first (defines the bar everything else measures against). Then U2, U3, U4, U5 can proceed in parallel — U2 is independent code work; U3/U4/U5 are parallel investigation tracks. U6 last, as it synthesizes U3 and U5 findings into the decision. The user's "crack Dragy first" intent means U3/U4/U5 are the priority investigative thrust; U2 is the safe-value deliverable that lands regardless of their outcome.
