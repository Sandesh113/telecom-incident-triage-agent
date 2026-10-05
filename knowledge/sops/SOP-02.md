---
doc_id: SOP-02
version: "0.5"
status: draft
source: "Telecom Incident Triage SOPs v0.5 (redline pending owner acceptance); text verbatim except where noted"
triggers: [HSS_UNREACHABLE, SUBSCRIBER_DATA_TIMEOUT, UDM_UNREACHABLE]
---

# [SOP-02] HSS or UDM subscriber-data failures

> summary: HSS or UDM subscriber-data failures: named function vs consumer path vs shared dependency (including UDR).

## [SOP-02.T] Trigger

> summary: Read to confirm this SOP applies.

HSS_UNREACHABLE, UDM_UNREACHABLE, or SUBSCRIBER_DATA_TIMEOUT; also a registration or authentication failure rise accompanied by a subscriber-data error.

## [SOP-02.Q] Investigation question

> summary: Read to frame the competing hypotheses for this SOP.

Is the named subscriber-data function failing, is one consumer path failing, or is a shared dependency responsible? The fixture must identify HSS or UDM; the report must preserve that distinction.

## [SOP-02.1] Step 1

> summary: Read when running SOP-02.1: Identify function, consumers, error codes, and event times.

step_type: read_only

**Check and required data.** Identify function, consumers, error codes, and event times. Requires function and consumer IDs.

**Supports a candidate.** Several consumers show matching errors against the function.

**Weakens a candidate.** One consumer fails while others continue succeeding.

## [SOP-02.2] Step 2

> summary: Read when running SOP-02.2: Compare function health with consumer-to-function reachability.

step_type: read_only

**Check and required data.** Compare function health with consumer-to-function reachability. Requires both observations. Where a UDM is involved, also compare UDM–UDR (N35) health and reachability before distinguishing a UDM fault from a UDR fault.

**Supports a candidate.** Function health degrades alongside the errors.

**Weakens a candidate.** Function health remains stable while one consumer path fails.

## [SOP-02.3] Step 3

> summary: Read when running SOP-02.3: Compare registration and authentication successes and failures before and after onset.

step_type: read_only

**Check and required data.** Compare registration and authentication successes and failures before and after onset. Requires counts and denominators in each 15-minute window.

**Supports a candidate.** Outcomes worsen for the mapped customer group.

**Weakens a candidate.** Outcomes remain stable with adequate attempts.

## [SOP-02.4] Step 4

> summary: Read when running SOP-02.4: Check dependent links and recent changes.

step_type: read_only

**Check and required data.** Check dependent links and recent changes. Requires change records and the function relationships in REF-CORE.5–REF-CORE.6.

**Supports a candidate.** A dependency matches the affected consumers and timing.

**Weakens a candidate.** Its scope or timing does not fit.

## [SOP-02.E] Escalation

> summary: Read when deciding escalation for SOP-02.

Escalate for significant or severe impact, or when registration or authentication failure rate rises ≥5 percentage points with ≥20 attempts in each comparison window. With fewer attempts, record inconclusive.

## [SOP-02.C] Change boundary

> summary: Read when deciding change boundary for SOP-02.

Function restart or configuration correction is change.
