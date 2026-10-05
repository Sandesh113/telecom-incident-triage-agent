---
doc_id: REF-RAN
version: "0.3"
status: draft
applies_to: Synthetic demo network "Albion Mobile"; SOP v0.3 (canonical); SKILL v0.4
rule_refs: shared-rules (SOP v0.3 §1) — RULES.1 routing, RULES.2 15-min event-time windows, RULES.3 5-min persistence sub-windows, RULES.4 late events, RULES.5 impact tiers, RULES.6 minimum samples, RULES.7 missing evidence, RULES.8 multiple causes, RULES.9 change control
sources: 3GPP TS 38.214 (§5.2.2.1 CQI), TS 38.331 (RRC measurement configuration), TS 38.300 (NR overall description), TS 36.213 (LTE CQI)
---

# RAN and RF reference (REF-RAN)

> summary: Handover KPI definitions, the RF mechanisms by which a frequency or neighbour change can cause failures, and the evidence each mechanism needs. Used by SOP-04 and SOP-05.

## [REF-RAN.1] Handover KPI definitions

> summary: Read during SOP-04.2 to compute and compare handover failure rates reproducibly.

**Handover stages:**
- *Preparation*: the source requests the target, and the target admits or rejects. A preparation failure means the target or signalling rejected the request or did not answer.
- *Execution*: the UE is commanded to move and must access the target. An execution failure means the UE did not complete access to the target.

Report the two stages separately. A configuration problem often shows in one stage more than the other.

**Scope.** Rates are calculated per source cell (all outgoing attempts) or per cell pair (source to target). State which one. SOP-04.2 uses per source cell, all stages combined, unless the fixture says otherwise; stage-level rates are supporting detail.

**Formula:**
- Failure rate (%) = failures ÷ attempts × 100, for one stage, one scope and one window.
- With zero attempts the rate is undefined; record the comparison as `inconclusive`.

**Minimum sample.** Before/after comparisons follow [RULES.6]. That minimum is a demo convention for consistency, not a guarantee of statistical significance. Rate thresholds live in SOP-04.2.

**Measurement setup.** Inter-frequency handover requires the target frequency to be configured for measurement and the neighbour relation to exist (TS 38.331).

## [REF-RAN.2] Candidate mechanisms after a frequency or neighbour change

> summary: Read when RF_FREQUENCY_CHANGE or NEIGHBOUR_CONFIG_CHANGE precedes handover failures or call drops. Each mechanism needs its own evidence.

| Candidate mechanism | Evidence to request | Notes |
|---|---|---|
| Interference (co-channel or adjacent-channel) | Carrier settings before and after; coverage overlap; quality trends (SINR, CQI, BLER); cell load; comparison cells | Sharing a carrier opens an interference investigation. It does not by itself support a harmful-interference conclusion. |
| PCI collision or confusion | Carrier and PCI assignments for the changed cell and its neighbours; neighbour relations; target-identification or wrong-target handover failures | Radio quality can look normal. Normal quality does not reject this mechanism. |
| Missing measurement or neighbour configuration | Executed configuration changes; measurement configuration for the new frequency; neighbour relations; handover-stage outcomes (preparation vs execution); missing or absent handover attempts | Radio quality can look normal. Normal quality does not reject this mechanism. |

Rules for this section:
- A change followed by a symptom is a lead, not proof (SOP-04).
- Keep each mechanism as a separate hypothesis until its own evidence supports or weakens it.
- Confirm from change records that the change was actually executed, and when, not just planned.

## [REF-RAN.3] Radio quality measurements

> summary: Read during SOP-04.3 to interpret SINR, CQI, BLER and related measurements reproducibly.

| Measurement | Direction and source | Interference tendency |
|---|---|---|
| RSRP | Downlink, UE-reported | Often unchanged |
| RSRQ | Downlink, UE-reported | Falls |
| SINR | Downlink (UE-reported) or uplink (gNB-measured); state which | Falls |
| CQI | Downlink, UE-reported | Falls |
| BLER | State direction, and whether it is initial-transmission BLER or residual BLER after retransmission | Initial BLER rises |
| UL noise / RSSI | Uplink, gNB-measured | Rises if the uplink is affected |

**Recording a measurement.** Every value must state:
- direction;
- sample count;
- aggregation (mean, median or percentile) over the window;
- the window itself.

Missing samples are `unable_to_check` ([RULES.7]).

**BLER targets.** The CQI error-probability target depends on the configured CQI table (TS 38.214 §5.2.2.1). The demo fixture states its target BLER explicitly. Do not assume a single value.

**Combining measurements.** One measurement alone does not establish interference (SOP-04.3). For the interference mechanism, look for SINR/CQI falling together with initial BLER rising, concentrated in the cells that overlap the changed cell.

## [REF-RAN.4] Spatial pattern

> summary: Read to decide whether degradation follows an RF neighbourhood or some other dependency.

- RF-related degradation tends to concentrate in the changed cell and its overlapping or related neighbours.
- Cells without a relevant RF relationship to the change can act as controls, provided they meet the control criteria in [REF-TX.1].
- Degradation outside the RF neighbourhood needs a different explanation, such as transport ([REF-TX.4]), or must be listed as unexplained.

**Baseline RF neighbour relations (Albion Mobile demo, topo-1, pre-change):**

| Cell | RF neighbours | Carrier | PCI |
|---|---|---|---|
| CELL-A | CELL-B | F1 | 110 |
| CELL-B | CELL-A, CELL-C | F1 | 150 |
| CELL-C | CELL-B, CELL-D | F1 | 101 |
| CELL-D | CELL-C | F2 | 205 |
| CELL-E | CELL-F | F1 | 120 |
| CELL-F | CELL-E | F2 | 230 |

These are the pre-change baseline values for this demo network. An executed RF change (SOP-04) alters a specific cell's carrier or PCI from this baseline; read the change record for the new value, never assume this table still holds after a change.

**Baseline measurement configuration (Albion Mobile demo, topo-1):**

| Cell | Frequencies configured for measurement |
|---|---|
| CELL-A | F1 |
| CELL-B | F1, F2 |
| CELL-C | F1, F2 |
| CELL-D | F1, F2 |
| CELL-E | F1, F2 |
| CELL-F | F1, F2 |

Used by SOP-04.5 and the "missing measurement or neighbour configuration" mechanism ([REF-RAN.2]): a handover to a frequency the target cell has no measurement configuration for will fail regardless of radio quality.

## [REF-RAN.5] Release causes and provenance

> summary: Read when separating radio-caused from transport- or core-caused drops.

- Radio-class releases: radio link failure, handover failure, timers expiring after losing the radio link.
- Transport- or core-class releases: N2/S1 association loss, user-plane path failure, core-initiated release.

Each CNE event carries:
- `raw_cause`: the cause as reported;
- `reporting_element`: which element reported it;
- `mapping_version`: the version of the cause-mapping table;
- `release_cause_class`: `radio` | `transport` | `core` | `other`.

The class is derived from `raw_cause` through the mapping table, never from the scenario answer key. Vendors classify causes differently, so treat the class as supporting evidence, not proof.

## [REF-RAN.6] Evidence the RAN checks need

> summary: Read to judge whether a RAN step can be run or must be recorded as unable_to_check.

- Change records: changed cell, parameter, old and new values, planned and executed time, execution status.
- Carrier and PCI assignments, and neighbour relations, valid at incident time (versioned).
- Measurement configuration for the affected frequencies.
- Handover attempts and failures by stage, scope and window, with denominators.
- Radio measurements with direction, sample count and aggregation.
- CNE events with release-cause provenance.
