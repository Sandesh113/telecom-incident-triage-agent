---
doc_id: REF-TX
version: "0.3"
status: draft
applies_to: Synthetic demo network "Albion Mobile"; SOP v0.3 (canonical); SKILL v0.4. First fixtures use single-path backhaul only (see REF-TX.1).
rule_refs: shared-rules (SOP v0.3 §1) — RULES.1 routing, RULES.2 15-min event-time windows, RULES.3 5-min persistence sub-windows, RULES.4 late events, RULES.5 impact tiers, RULES.6 minimum samples, RULES.7 missing evidence, RULES.8 multiple causes, RULES.9 change control
sources: IETF RFC 5880 (BFD); 3GPP TS 38.413 (NGAP), TS 29.281 (GTP-U)
---

# Transport reference (REF-TX)

> summary: Backhaul dependencies, how to count link state transitions, and what transport faults can do to RAN and core. Used by SOP-03, SOP-04.4 and SOP-05.

## [REF-TX.1] Backhaul dependencies and control cells

> summary: Read before attributing any cell or service to a link, or choosing control cells. Impact can only follow dependencies that were active at incident time.

- Path: cell → gNB/eNB → cell-site router (CSR) → backhaul link(s) → aggregation router → core.
- **First fixtures: single-path only.** Each cell has one `backhaul_path` (an ordered list of link IDs), valid for a stated topology version and time range.
- **Demo topology (SOP v0.3 §8):** LINK-1 → CELL-A, CELL-B; LINK-2 → CELL-C, CELL-D; LINK-3 → CELL-E, CELL-F. When LINK-1 flaps and CELL-C/D have coincident RF symptoms, CELL-E/F are the transport controls. Controls need their own outcome measurements; naming them in the topology is not enough.
- **If dual paths are added later,** each cell must record:
  - `primary_path` and `alternate_path`;
  - their shared segments;
  - `active_path` at incident time.

  A failed link on a standby path must not receive customer-impact attribution on that basis alone.
- A cell depends on a link only if that link is on its active path at incident time.
- **A suitable control cell** must meet all three conditions:
  - its active path does not include the link;
  - it shares no upstream segment with the affected cells;
  - it has no coincident RF change or RF exposure.

  A different link alone does not make a cell a valid control.

## [REF-TX.2] Link state model and transition counting

> summary: Read during SOP-03.1 to count transitions correctly.

**Object types.** Keep these distinct; each has its own state:
- physical port;
- BFD session;
- LAG member;
- aggregate link (LAG).

A BFD session going down shows that the monitored forwarding path failed (RFC 5880). It does not by itself identify a physical fibre failure.

**Counting rules for one object:**
1. Deduplicate by event ID.
2. Order by event time. Late events follow [RULES.4]: place them by event_time, flag `late_event` when ingest_time − event_time exceeds 5 minutes, recalculate the affected windows, and issue a new report version if a finding or escalation changes.
3. The initial state is the object's last known state before the window starts, taken from the state snapshot. If it is unknown, record the first in-window report as establishing state, not as a transition.
4. A transition is counted only when the state actually changes. Repeated reports of the same state, even from different events, are not transitions.
5. A transition belongs to the window that contains its event time. Windows are half-open: start inclusive, end exclusive.
6. A down followed by an up is two transitions.

The continuing-flap threshold is defined in SOP-03 (not repeated here, to avoid drift). Being below it changes escalation; it does not show the link had no impact.

Some devices damp repeated flaps, which suppresses events. Damping is vendor-specific; where it is configured, the demo topology records `damping: true`.

## [REF-TX.3] What a backhaul fault can do downstream

> summary: Read when deciding whether cell or customer symptoms are consistent with a transport cause.

| Layer | Possible symptom while the backhaul is down or flapping |
|---|---|
| RAN to core control (N2/S1-MME, SCTP) | SCTP association loss or resets; the cell may briefly lose service |
| RAN to core user plane (N3/S1-U, GTP-U) | GTP-U path failures, packet loss, stalled sessions |
| RAN to RAN (Xn/X2) | Handovers between affected sites may fail |
| Customer experience | Call drops and session failures, often with transport- or core-related release causes |

**Interpreting radio measurements:**
- Stable radio measurements on the affected cells strengthen a transport-only explanation.
- Degraded radio measurements warrant a concurrent RF investigation. They do not exclude transport impact.
- Missing radio samples are `unable_to_check`.

## [REF-TX.4] Transport vs RF: competing hypotheses

> summary: Read when transport and RF hypotheses compete for the same cells (S3, S4).

| Evidence | Supports transport | Supports RF |
|---|---|---|
| Which cells | Cells whose active path contains the link | Cells in the RF neighbourhood of the changed cell |
| When | Aligned with each state transition; oscillating | Starting after the change time; persistent |
| Radio measurements | Stable measurements strengthen it | Mechanism-specific evidence ([REF-RAN.2]) |
| Release causes (with provenance) | Transport- or core-class causes | Radio-class causes |

**A cell exposed to both dependencies:**
- Retain both hypotheses for it.
- Attribute its symptoms to each only where that mechanism's own evidence supports it.
- If the contributions cannot be separated, report the attribution as unresolved ([REF-CORR.2]).

## [REF-TX.5] Evidence the transport checks need

> summary: Read to judge whether a transport step can be run or must be recorded as unable_to_check.

- Link events: object ID, object type (port, BFD session, LAG member, aggregate), state, event_id, event_time, ingest_time.
- Last known state of each object before the window.
- Topology version valid at incident time: active path per cell, service-to-link mappings, redundancy model.
- Per-cell outcome time series in 15-minute event-time windows ([RULES.2]), with sample counts, for both dependent and control cells.
- Change records (transport and RF) in the same window, with executed-change status.
