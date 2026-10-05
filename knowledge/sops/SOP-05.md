---
doc_id: SOP-05
version: "0.5"
status: draft
source: "Telecom Incident Triage SOPs v0.5 (redline pending owner acceptance); text verbatim except where noted"
triggers: [CALL_DROP_RISE, CNE_INCIDENT, CUSTOMER_COMPLAINT]
---

# [SOP-05] Customer network experience and multi-cause triage

> summary: Customer network experience and multi-cause triage: impact groups, attribution states, unexplained symptoms.

## [SOP-05.T] Trigger

> summary: Read to confirm this SOP applies.

CNE_INCIDENT, CALL_DROP_RISE, a customer complaint (CUSTOMER_COMPLAINT), or concurrent domain SOP triggers with overlapping affected scope.

## [SOP-05.Q] Investigation question

> summary: Read to frame the competing hypotheses for this SOP.

Which customer and cell groups are affected, which supported cause explains each group, and what remains unexplained?

## [SOP-05.1] Step 1

> summary: Read when running SOP-05.1: Group distinct affected customers by cell, service, and 15-minute event-time window.

step_type: read_only

**Check and required data.** Group distinct affected customers by cell, service, and 15-minute event-time window. Requires deduplicated impact/customer IDs, enterprise flags, and mapping.

**Supports a candidate.** A candidate’s dependency scope covers that affected group.

**Weakens a candidate.** Affected cells or services fall outside its scope.

## [SOP-05.2] Step 2

> summary: Read when running SOP-05.2: Run relevant domain SOPs and keep their findings and citations separate.

step_type: read_only

**Check and required data.** Run relevant domain SOPs and keep their findings and citations separate.

**Supports a candidate.** Independent transport and RF evidence support separate causes for separate groups.

**Weakens a candidate.** One shared dependency with matching scope and measurements supports one cause.

## [SOP-05.3] Step 3

> summary: Read when running SOP-05.3: Assign each material symptom to one of four states: single (one supported candidate), multiple (several candidates, each with its own mechanism evidence), unresolved (contributions cannot be separated), or unexplained.

step_type: read_only

**Check and required data.** Assign each material symptom to one of four states: single (one supported candidate), multiple (several candidates, each with its own mechanism evidence), unresolved (contributions cannot be separated), or unexplained. Requires the complete affected-object list.

**Supports a candidate.** Each assignment cites the relevant reference-file relationship (REF-TX.1, REF-CORE.5–6, or REF-RAN.4) and measurement evidence. An object exposed to two dependencies keeps both candidates; exposure alone is not attribution.

**Weakens a candidate.** An assignment relies only on approximately simultaneous events.

## [SOP-05.4] Step 4

> summary: Read when running SOP-05.4: Calculate the impact tier from distinct customers and enterprise flags.

step_type: read_only

**Check and required data.** Calculate the impact tier from distinct customers and enterprise flags.

**Supports a candidate.** ≥500 or ≥2 enterprises: severe. Otherwise ≥100 or 1 enterprise: significant.

**Weakens a candidate.** Below threshold affects priority; it does not refute a fault. Missing counts give impact_tier_unknown.

## [SOP-05.E] Escalation

> summary: Read when deciding escalation for SOP-05.

Escalate severe impact immediately for engineer review. Also escalate significant impact or material symptoms that remain unexplained after relevant checks.

## [SOP-05.O] Output

> summary: Read when deciding output for SOP-05.

One or more cause hypotheses, the affected group for each, supporting and conflicting event IDs, an attribution state for every affected object, and a separate unexplained-symptom list. Corrective network action is change.
