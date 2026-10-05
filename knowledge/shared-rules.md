---
doc_id: RULES
version: "0.5"
status: draft
source: "Telecom Incident Triage SOPs v0.5 §1–§2 (redline pending owner acceptance); rule text verbatim"
---

# Shared rules and routing (RULES)

> summary: Rules that apply to every SOP, and the trigger-to-SOP routing table. Read [RULES.1]–[RULES.9] before any SOP and [ROUTING] before selecting SOPs.

## [RULES.1] Route from normalized events

> summary: Read first: triggers come from the alarm dictionary and select candidate SOPs, never causes; investigation vs escalation thresholds.

Route from normalized events. The alarm dictionary maps source alarms to the trigger names in Section 2. A trigger selects a candidate SOP; it does not establish a root cause. Multiple SOPs may run for one incident. KPI-derived investigation triggers use a lower demo threshold (a rise of ≥3 percentage points, with ≥20 attempts in each 15-minute window) than the SOP escalation thresholds (≥5 percentage points). A trigger starts an investigation; it does not imply escalation.

## [RULES.2] Use event time

> summary: Read when windowing or deduplicating: 15-minute event-time windows.

Use event time. Evaluate impact and most trends in rolling 15-minute windows. Deduplicate repeated event IDs before counting.

## [RULES.3] Use 5-minute windows only for persistence

> summary: Read for SOP-01 persistence: 5-minute sub-windows.

Use 5-minute windows only for persistence. SOP-01’s persistence check uses two consecutive, non-overlapping 5-minute sub-windows for the same PCF–SMF pair. The synthetic generator must provide policy results at 5-minute granularity. Other checks continue to use the stated 15-minute windows unless an SOP specifies otherwise.

## [RULES.4] Include late events and revise findings

> summary: Read when an event arrives late or a finding may need a new report version.

Include late events and revise findings. Place every event in the window determined by its event time, even if it arrives later. Flag it as late_event when ingest_time − event_time > 5 minutes. Recalculate affected windows after a late event arrives. If a draft RCA’s finding or escalation level changes, issue a new report version that identifies the superseded version.

## [RULES.5] Apply mutually exclusive escalation tiers

> summary: Read when calculating the impact tier (severe, significant, below tiers, unknown).

Apply mutually exclusive escalation tiers.

- Severe: ≥500 distinct affected customers in 15 minutes, or ≥2 distinct affected enterprise customers.
- Significant: If not severe, ≥100 distinct affected customers in 15 minutes, or 1 affected enterprise customer.
- Below these tiers: Continue investigation; a low count does not refute a fault.

Count each customer once per window. If the data cannot establish a tier, report impact_tier_unknown; do not assume low impact.

## [RULES.6] Require adequate samples

> summary: Read before any before/after rate comparison: minimum attempts.

Require adequate samples. A before/after failure-rate comparison needs ≥20 attempts in each comparison window. Otherwise its result is inconclusive.

## [RULES.7] Record missing evidence

> summary: Read when required data is missing: unable_to_check.

Record missing evidence. A check without its required data returns unable_to_check. Missing data neither supports nor refutes a hypothesis.

## [RULES.8] Allow multiple causes

> summary: Read when assigning causes: multiple causes and unexplained symptoms.

Allow multiple causes. Assign a cause only to the cells and services its evidence can explain. List remaining symptoms as unexplained.

## [RULES.9] Control changes

> summary: Read before proposing any action: read_only vs change.

Control changes. Investigation steps are read_only. Restarts, rollbacks, routing or configuration changes, and physical intervention are change actions requiring engineer approval.

## [ROUTING] Trigger-to-SOP routing

> summary: Read before selecting SOPs. Maps normalized triggers to candidate SOPs; all matching SOPs are recorded.

| Normalized trigger | Candidate SOP |
|---|---|
| N7_TIMEOUT, PCF_POLICY_REQUEST_FAILURE, PCF_UNREACHABLE | SOP-01 |
| VOICE_SETUP_FAILURE_RISE and a mapped policy-service dependency where the service map identifies the voice service, policy_function = PCF, and the N5/N7 interface | SOP-01 |
| HSS_UNREACHABLE, UDM_UNREACHABLE, SUBSCRIBER_DATA_TIMEOUT | SOP-02 |
| Registration or authentication failure rise (REGISTRATION_FAILURE_RISE, AUTHENTICATION_FAILURE_RISE) with a subscriber-data error in the same service and subscriber-function scope, within 15 minutes | SOP-02 |
| TRANSPORT_LINK_FLAP, LINK_DOWN, LINK_UP | SOP-03 |
| RF_FREQUENCY_CHANGE or NEIGHBOUR_CONFIG_CHANGE, followed within 30 minutes by HANDOVER_FAILURE_RISE, CALL_DROP_RISE, or a mapped CNE event | SOP-04 |
| CNE_INCIDENT, CALL_DROP_RISE, a customer complaint (CUSTOMER_COMPLAINT), or concurrent domain SOP triggers with overlapping affected scope | SOP-05 |

The router records all matching SOPs. Later evidence may add an SOP; it must not silently discard one that was triggered. An RF_FREQUENCY_CHANGE or NEIGHBOUR_CONFIG_CHANGE alone is context. SOP-04 is selected only when enrichment emits SOP04_ELIGIBLE: an executed change followed by a symptom on the changed cell or a neighbour, with 0 ≤ symptom event_time − executed_time ≤ 30 minutes (event time, never ingest time).
