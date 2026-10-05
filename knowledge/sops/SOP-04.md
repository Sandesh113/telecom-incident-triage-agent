---
doc_id: SOP-04
version: "0.5"
status: draft
source: "Telecom Incident Triage SOPs v0.5 (redline pending owner acceptance); text verbatim except where noted"
triggers: [CALL_DROP_RISE, HANDOVER_FAILURE_RISE, NEIGHBOUR_CONFIG_CHANGE, RF_FREQUENCY_CHANGE]
---

# [SOP-04] Handover failures after an RF change

> summary: Handover failures after an RF change: interference, PCI and neighbour/measurement-configuration mechanisms.

## [SOP-04.T] Trigger

> summary: Read to confirm this SOP applies.

RF_FREQUENCY_CHANGE or NEIGHBOUR_CONFIG_CHANGE followed within 30 minutes by HANDOVER_FAILURE_RISE, CALL_DROP_RISE, or a mapped CNE event.

## [SOP-04.Q] Investigation question

> summary: Read to frame the competing hypotheses for this SOP.

Does changed-cell and neighbour evidence support an RF-related cause, or does another fault better explain some affected cells?

## [SOP-04.1] Step 1

> summary: Read when running SOP-04.1: Read changed cell, old/new setting, change time, and neighbour relations.

step_type: read_only

**Check and required data.** Read changed cell, old/new setting, change time, and neighbour relations.

**Supports a candidate.** Degraded cells have a relevant changed-cell or neighbour relationship.

**Weakens a candidate.** Degraded cells fall outside that relationship.

## [SOP-04.2] Step 2

> summary: Read when running SOP-04.2: Compare per-cell handover attempts and failures before and after the change.

step_type: read_only

**Check and required data.** Compare per-cell handover attempts and failures before and after the change.

**Supports a candidate.** With ≥20 attempts in each window, failure rate rises ≥5 percentage points and reaches ≥10% afterward.

**Weakens a candidate.** Failure rate remains stable with adequate attempts.

## [SOP-04.3] Step 3

> summary: Read when running SOP-04.3: Interference mechanism only.

step_type: read_only

**Check and required data.** Interference mechanism only. Compare CQI, SINR, and BLER before and after for changed and neighbouring cells.

**Supports a candidate.** Measurements worsen in a spatial pattern consistent with the RF hypothesis.

**Weakens a candidate.** Measurements remain stable with adequate coverage. One metric alone is insufficient to establish interference. Stable measurements weaken the interference mechanism only; they do not weaken PCI or neighbour/measurement-configuration mechanisms (SOP-04.5).

## [SOP-04.4] Step 4

> summary: Read when running SOP-04.4: Inspect mapped transport links and link events.

step_type: read_only

**Check and required data.** Inspect mapped transport links and link events.

**Supports a candidate.** A link fault independently explains some affected cells.

**Weakens a candidate.** No matching transport evidence is observed, subject to telemetry completeness.

## [SOP-04.5] Step 5

> summary: Read when running SOP-04.5: Check PCI and carrier assignments for the changed cell and its neighbours, neighbour relations, measurement configuration for the new frequency, and handover outcomes by stage (preparation vs execution).

step_type: read_only

**Check and required data.** Check PCI and carrier assignments for the changed cell and its neighbours, neighbour relations, measurement configuration for the new frequency, and handover outcomes by stage (preparation vs execution). Requires executed-change records, PCI/carrier assignments and stage-level handover counts.

**Supports a candidate.** A PCI conflict on the shared carrier, a missing neighbour relation or measurement object, or stage-specific failures (for example wrong-target or absent attempts) support a PCI or configuration mechanism, even when radio quality is normal.

**Weakens a candidate.** Assignments and configuration are consistent, and handover stages show no specific failure pattern, with adequate attempts.

## [SOP-04.E] Escalation

> summary: Read when deciding escalation for SOP-04.

Escalate for significant or severe impact, or when the rate condition in SOP-04.2 is met. Treat the RF change as a candidate until mobility, neighbour, and measurement evidence align. Keep interference, PCI, and neighbour/measurement-configuration mechanisms as separate hypotheses until their own evidence discriminates.

## [SOP-04.C] Change boundary

> summary: Read when deciding change boundary for SOP-04.

Frequency rollback is change.
