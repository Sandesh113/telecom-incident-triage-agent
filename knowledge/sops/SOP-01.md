---
doc_id: SOP-01
version: "0.5"
status: draft
source: "Telecom Incident Triage SOPs v0.5 (redline pending owner acceptance); text verbatim except where noted"
triggers: [N7_TIMEOUT, PCF_POLICY_REQUEST_FAILURE, PCF_UNREACHABLE, VOICE_SETUP_FAILURE_RISE]
---

# [SOP-01] PCF and policy-service failures

> summary: PCF and policy-service failures: PCF service fault vs SMF-to-PCF path vs shared dependency.

## [SOP-01.T] Trigger

> summary: Read to confirm this SOP applies.

N7_TIMEOUT, PCF_POLICY_REQUEST_FAILURE, or PCF_UNREACHABLE. VOICE_SETUP_FAILURE_RISE also selects this SOP only when the fictional service map identifies the voice service (VoLTE or VoNR), policy_function = PCF, and the N5/N7 interface. If the voice path uses a PCRF (Rx/Gx), record a routing mismatch; PCRF investigation is out of scope for this demo.

## [SOP-01.Q] Investigation question

> summary: Read to frame the competing hypotheses for this SOP.

Is the evidence more consistent with a PCF service fault, one SMF-to-PCF path fault, or another shared dependency?

## [SOP-01.1] Step 1

> summary: Read when running SOP-01.1: Compare policy successes, failures, and timeouts per SMF before and after onset.

step_type: read_only

**Check and required data.** Compare policy successes, failures, and timeouts per SMF before and after onset. Requires timestamped per-SMF counts.

**Supports a candidate.** Several SMFs show concurrent failure rises, supporting a shared-fault candidate.

**Weakens a candidate.** Failures confined to one SMF weaken a shared PCF-fault explanation.

## [SOP-01.2] Step 2

> summary: Read when running SOP-01.2: Compare PCF health with reachability from each SMF.

step_type: read_only

**Check and required data.** Compare PCF health with reachability from each SMF. Requires PCF health and path observations.

**Supports a candidate.** PCF degradation alongside failures from several SMFs supports a PCF-fault candidate.

**Weakens a candidate.** Healthy PCF observations with failure on one path favour investigating that path.

## [SOP-01.3] Step 3

> summary: Read when running SOP-01.3: Compare mapped service and customer/session outcomes.

step_type: read_only

**Check and required data.** Compare mapped service and customer/session outcomes. Requires service dependencies and outcome counts.

**Supports a candidate.** Services dependent on the affected policy path degrade at the relevant time.

**Weakens a candidate.** A supposedly affected service has no such dependency, or remains stable with adequate data.

## [SOP-01.4] Step 4

> summary: Read when running SOP-01.4: Review shared transport and change events.

step_type: read_only

**Check and required data.** Review shared transport and change events. Requires change records and the shared-dependency relationships in REF-CORE.6.

**Supports a candidate.** Their time and affected scope match the policy failures.

**Weakens a candidate.** Their scope or event order does not fit.

## [SOP-01.E] Persistence and escalation

> summary: Read when deciding persistence and escalation for SOP-01.

For a given PCF–SMF pair, persistence means ≥3 failed policy requests in each of two consecutive, non-overlapping 5-minute sub-windows. Escalate when that condition is met or impact is significant or severe. Keep PCF, single-path, and shared-dependency explanations separate until the evidence discriminates between them.

## [SOP-01.C] Change boundary

> summary: Read when deciding change boundary for SOP-01.

A restart or configuration correction is change. The agent may draft a recommendation for engineer review; it cannot execute it.
