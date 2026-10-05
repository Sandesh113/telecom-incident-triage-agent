---
doc_id: REF-CORR
version: "0.3"
status: draft
applies_to: Synthetic demo network "Albion Mobile"; SOP v0.3 (canonical); SKILL v0.4
rule_refs: shared-rules (SOP v0.3 §1) — RULES.1 routing, RULES.2 15-min event-time windows, RULES.3 5-min persistence sub-windows, RULES.4 late events, RULES.5 impact tiers, RULES.6 minimum samples, RULES.7 missing evidence, RULES.8 multiple causes, RULES.9 change control
sources: Cascade pattern from AWS for Industries, "Building AI Agents for Telecom Network Operations" (22 Sep 2026): group by site, sort by event time, match infrastructure keywords
---

# Event correlation patterns (REF-CORR)

> summary: How to treat candidate root causes versus symptoms, shared versus independent faults, and evidence versus coincidence. Used mainly by SOP-05, and by any SOP with competing hypotheses.

## [REF-CORR.1] Cascades and the earliest-event heuristic

> summary: Read when many alarms arrive in a short window and may share one cause.

- One infrastructure fault can produce symptoms downstream.
- Heuristic: the earliest infrastructure-level event in a connected scope is a **candidate** root cause, and later events in that scope are **candidate** symptoms. Treat both as hypotheses.
- Why the earliest observed event may not be the earliest failure:
  - delayed alarm detection;
  - clock differences between reporting elements;
  - different collection or polling intervals;
  - late-arriving events.

  Even sorting by event time cannot guarantee that the first observed alarm represents the first underlying failure.
- Late events follow [RULES.4]: place by event_time, flag `late_event` when ingest_time − event_time exceeds 5 minutes, recalculate the affected windows, and issue a new report version if a finding or escalation changes.
- Group by site, then match each alarm's summary against infrastructure-level keywords (PFCP Path, GTP Path Failure, SCTP, Link Failure, Power, Card, Configuration Modified, and similar). The earliest infrastructure-level alarm at a site is the candidate root cause; later alarms at that site are candidate symptoms (AWS for Industries cascade-detection pattern).
- Protocol-specific cascades need their own checks. For example, an N4/PFCP failure and a concurrent GTP-C path failure are not assumed to be cause and symptom ([REF-CORE.7]).

## [REF-CORR.2] Shared-fault vs independent-fault hypotheses

> summary: Read whenever more than one hypothesis is plausible for the same window (S3, S4).

First test scope: could one dependency explain every affected object?

| Finding | Interpretation |
|---|---|
| One dependency covers all affected objects, with consistent timing and measurements | Supports a shared-fault hypothesis |
| Affected objects split into groups, each matched by a different dependency and its own mechanism evidence | Supports independent-fault hypotheses |
| A group matched by no supported hypothesis | Unexplained; list it separately |
| An object exposed to two dependencies | Retain both hypotheses for that object (see below) |

**Objects exposed to two dependencies.** Being behind a flapping link and being an RF neighbour establishes two possible exposures. It does not establish that both faults caused that object's symptoms.
- Attribute the symptoms to each hypothesis only where its own measurements support that mechanism.
- If the contributions cannot be separated, report the attribution as `unresolved`.

Occurring in the same window is not enough to merge two groups into one cause.

## [REF-CORR.3] Flaps, transients and sustained faults

> summary: Read when events repeat or clear quickly.

- **Flap:** repeated state transitions of one object. Count them using [REF-TX.2].
- **Sustained fault:** stays in the failed state.
- **Transient fault:** clears within the window. Its impact can still be real and must be assessed.
- Being below a flap threshold changes escalation, not whether a fault occurred (SOP-03 below-threshold outcome).

## [REF-CORR.4] Change-induced degradation

> summary: Read when a configuration or RF change precedes the symptoms.

- Confirm from change records that the change was executed, and when.
- Look for symptoms that start after the executed change, in the objects the change could affect.
- Before treating the change as a cause, confirm the relevant dependency (neighbour relation, path or configuration scope) and the mechanism-specific evidence ([REF-RAN.2]).
- Symptoms that started before the change, or in objects the change cannot affect, weaken the change hypothesis.
- Rolling back is a change action and requires engineer approval ([RULES.9]).

## [REF-CORR.5] Coincidence and data traps

> summary: Read when evidence looks convincing but may be misleading.

- **Unrelated concurrency.** Two faults in the same window that are unrelated to each other.
- **Noise.** Low-severity events unrelated to the incident.
- **Late arrivals.** Ordering by arrival time instead of event time distorts the sequence ([RULES.4]).
- **Identifier aliases.** The same element under two names (for example `PCF-02` and `pcf2.core`). Resolve through the alias table before grouping; list unresolved IDs rather than dropping them.
- **Stale topology.** Relationships that were not valid at incident time. Use the topology version for that time.
- **Missing telemetry.** Absence of evidence is `unable_to_check`; it neither supports nor weakens a hypothesis ([RULES.7]).
- **Leaked labels.** Derived fields (such as release-cause class) must come from raw data through a versioned mapping, never from the scenario answer key ([REF-RAN.5]).

## [REF-CORR.6] Attribution and the unexplained remainder

> summary: Read during SOP-05.3 when assigning every affected object.

- Every material symptom ends in exactly one of four states:
  - attributed to one supported hypothesis;
  - attributed to more than one hypothesis, each with its own mechanism evidence;
  - attribution unresolved between named hypotheses;
  - unexplained.
- Each attribution must cite the relevant reference-file relationship (REF-TX.1 backhaul mapping, REF-CORE.5–6 function dependencies, or REF-RAN.4 RF neighbourhood) and measurement evidence. Timing alone is not enough.
- Report the unexplained list even when it is empty. An honest "unexplained" is a valid result ([RULES.8]).

## [REF-CORR.7] Typical evidence by fault type

> summary: Read for a one-table comparison of the evidence that typically supports each hypothesis type. Tendencies, not requirements.

| Hypothesis type | Scope | Timing | Typical supporting evidence | Release-cause class (with provenance) |
|---|---|---|---|---|
| PCF / policy | Sessions using the affected policy function and pool, across sites | Onset across several SMFs together | Policy failures and timeouts with PCF health degradation ([REF-CORE.4]) | core |
| HSS / UDM | Procedures needing the named function, across many cells | Aligned with the function's health event | Registration or authentication failures from several consumers ([REF-CORE.5]) | core |
| Backhaul flap | Cells whose active path contains the link | Aligned with state transitions | Transitions counted per [REF-TX.2]; stable radio measurements strengthen it, but are not required | transport |
| RF: interference | Changed cell plus overlapping neighbours | After the executed change; persistent | SINR/CQI falling with initial BLER rising, relative to comparison cells | radio |
| RF: PCI collision/confusion | Changed cell and neighbours sharing carrier and PCI | After the executed change | Conflicting PCI assignments; wrong-target or target-identification failures; radio quality may be normal | radio |
| RF: missing measurement/neighbour configuration | Changed cell and the neighbours it should hand over to | After the executed change | Missing measurement configuration or neighbour relation; stage-specific handover outcomes; radio quality may be normal | radio |
