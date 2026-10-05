---
doc_id: SOP-03
version: "0.5"
status: draft
source: "Telecom Incident Triage SOPs v0.5 (redline pending owner acceptance); text verbatim except where noted"
triggers: [LINK_DOWN, LINK_UP, TRANSPORT_LINK_FLAP]
---

# [SOP-03] Backhaul link flap

> summary: Backhaul link flap: transition counting, dependent vs control cells, continuing-flap threshold.

## [SOP-03.T] Trigger

> summary: Read to confirm this SOP applies.

TRANSPORT_LINK_FLAP, LINK_DOWN, or LINK_UP.

## [SOP-03.Q] Investigation question

> summary: Read to frame the competing hypotheses for this SOP.

Did the link affect its dependent cells or services, and is the flap continuing? One state transition triggers investigation. At least five distinct down/up state transitions in 15 minutes define a continuing flap for this demo. A down followed by an up counts as two transitions, not two cycles.

## [SOP-03.1] Step 1

> summary: Read when running SOP-03.1: Deduplicate and count link state transitions.

step_type: read_only

**Check and required data.** Deduplicate and count link state transitions. Requires link ID, state, event ID, and event time. If individual transitions are not observable (enrichment flag transition_observability_incomplete, for example device damping), record the threshold as unable_to_check, not as below threshold.

**Supports a candidate.** ≥5 transitions/15 minutes meets the continuing-flap definition.

**Weakens a candidate.** Fewer than five is below that threshold; it does not prove no impact.

## [SOP-03.2] Step 2

> summary: Read when running SOP-03.2: Read cell-to-link and service-to-link mappings.

step_type: read_only

**Check and required data.** Read cell-to-link and service-to-link mappings from REF-TX.1.

**Supports a candidate.** Degraded objects depend on the flapping link.

**Weakens a candidate.** A degraded object has no mapped dependency and needs a separate explanation.

## [SOP-03.3] Step 3

> summary: Read when running SOP-03.3: Compare outcomes on dependent cells with control cells not served by the flapping link, that share no upstream segment with the affected cells, and that have no coincident RF change or RF exposure (REF-TX.1).

step_type: read_only

**Check and required data.** Compare outcomes on dependent cells with control cells not served by the flapping link, that share no upstream segment with the affected cells, and that have no coincident RF change or RF exposure (REF-TX.1). Requires per-cell, timestamped outcomes for both groups.

**Supports a candidate.** Dependent cells degrade after transitions while suitable control cells remain stable.

**Weakens a candidate.** Dependent cells remain stable with adequate observations, or degradation predates transitions.

## [SOP-03.4] Step 4

> summary: Read when running SOP-03.4: Inspect coincident RF changes and other transport faults.

step_type: read_only

**Check and required data.** Inspect coincident RF changes and other transport faults. Requires change records and the backhaul mapping in REF-TX.1.

**Supports a candidate.** Another event explains symptoms outside this link’s scope.

**Weakens a candidate.** No matching alternative appears; retain uncertainty if telemetry is incomplete.

## [SOP-03.E] Escalation

> summary: Read when deciding escalation for SOP-03.

Escalate for ≥5 transitions/15 minutes or significant or severe customer impact, whichever occurs first.

## [SOP-03.B] Below-threshold outcome

> summary: Read when deciding below-threshold outcome for SOP-03.

For a short flap below the threshold, report “below continuing-flap threshold”, assess observed impact, and identify any further checks. Do not conclude “no fault” solely from the transition count.

## [SOP-03.C] Change boundary

> summary: Read when deciding change boundary for SOP-03.

Route changes and physical intervention are change.
