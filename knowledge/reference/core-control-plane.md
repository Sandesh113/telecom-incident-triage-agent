---
doc_id: REF-CORE
version: "0.3"
status: draft
applies_to: Synthetic demo network "Albion Mobile"; SOP v0.3 (canonical); SKILL v0.4
rule_refs: shared-rules (SOP v0.3 §1) — RULES.1 routing, RULES.2 15-min event-time windows, RULES.3 5-min persistence sub-windows, RULES.4 late events, RULES.5 impact tiers, RULES.6 minimum samples, RULES.7 missing evidence, RULES.8 multiple causes, RULES.9 change control
sources: 3GPP TS 23.501 (5G architecture, incl. §4.2.5–4.2.7 and Annex E), TS 23.502 (procedures), TS 29.512 (PCF SM policy control), TS 29.244 (PFCP), TS 29.274 (GTPv2-C), TS 29.212 (Gx), TS 29.214 (Rx), TS 29.272 (S6a)
---

# Core control plane reference (REF-CORE)

> summary: Definitions and failure semantics for PCF, SMF, UDM, UDR, HSS, NRF and SCP that SOP-01 and SOP-02 rely on. Read a section only when a SOP step needs the meaning of an interface, function or symptom.

Behaviour that depends on vendor configuration is marked as such. Demo fixtures state that configuration explicitly; the agent must not assume it.

## [REF-CORE.1] Function roles

> summary: Read to identify which core function owns which job before forming a hypothesis.

| Function | Generation | Role relevant to triage |
|---|---|---|
| AMF | 5GC | Registration, mobility, NAS signalling; N2 (NGAP over SCTP) to the gNB |
| SMF | 5GC | PDU session management; policy requests to PCF over N7; controls UPF over N4 (PFCP) |
| UPF | 5GC | User-plane forwarding; N3 (GTP-U) from the gNB, N4 from the SMF |
| PCF | 5GC | Policy and QoS decisions: N7 to SMF, N5 from the application function |
| PCRF | EPC | 4G policy function: Gx to PGW, Rx from P-CSCF |
| UDM | 5GC | Subscriber-management services to AMF (N8), SMF (N10) and AUSF (N13) |
| UDR | 5GC | Data store accessed by UDM and other functions; UDM–UDR is N35 |
| AUSF | 5GC | Runs 5G authentication using data obtained from UDM |
| HSS | EPC / IMS | Subscriber and authentication data for the MME (S6a, Diameter) and IMS (Cx) |
| NRF | 5GC | Network function registration and discovery |
| SCP | 5GC | Optional: mediates service requests in indirect communication |

HSS and UDM are different functions, as are UDM and UDR. Some vendors deploy combinations, but an incident must name the function that actually failed (SOP-02).

## [REF-CORE.2] N7 and policy requests (SMF to PCF)

> summary: Read when N7_TIMEOUT or PCF_POLICY_REQUEST_FAILURE appears, to understand which session operations depend on policy.

- The SMF requests session-management policy from the PCF when a session is created and when it is modified.
- `N7_TIMEOUT`: the SMF sent a policy request and received no answer in time.
- `PCF_POLICY_REQUEST_FAILURE`: the PCF answered with an error.
- What the SMF does without a policy answer is vendor-configurable: it may reject the operation or apply a local policy. The demo topology records this per SMF in `failure_handling` (`reject` | `local_policy`).
- Whether existing sessions or other data sessions continue depends on which policy operation failed and on `failure_handling`. Do not assume either way.

## [REF-CORE.3] Voice dependency on policy (VoLTE / VoNR)

> summary: Read when VOLTE_SETUP_FAILURE_RISE coincides with policy failures, to decide whether the voice failures depend on the policy path under investigation.

- 5G voice (VoNR): the IMS application function (P-CSCF) requests policy from the PCF over N5; the PCF instructs the SMF over N7 to create the voice QoS flow (5QI 1).
- 4G voice (VoLTE): the P-CSCF requests policy from the PCRF over Rx; the PCRF instructs the PGW over Gx to create the voice bearer (QCI 1).
- Before attributing voice failures to SOP-01 (which investigates PCF/N7), the event or service map must identify:
  - the voice service (`VoLTE` | `VoNR`);
  - the policy function (`PCRF` | `PCF`);
  - the interface actually involved (`Rx/Gx` | `N5/N7`).
- If the voice path uses PCRF over Rx/Gx, a PCF/N7 investigation does not apply. Report a routing mismatch instead.
- Voice failures can also have IMS causes outside this reference. Attribute them to policy only where the service map shows the dependency.

## [REF-CORE.4] PCF service fault vs single-path fault

> summary: Read during SOP-01.1 and SOP-01.2 to interpret per-SMF failure patterns.

| Observation | Supports |
|---|---|
| Failures rise together across several SMFs, and PCF health is degraded | A PCF service-fault hypothesis |
| Failures on one SMF only, and PCF healthy for other SMFs | A hypothesis about that SMF-to-PCF path or that SMF |
| Failures across several SMFs, PCF health normal, discovery or routing errors present | A shared-dependency hypothesis (discovery, SCP mediation or transport; see [REF-CORE.6]) |

## [REF-CORE.5] HSS / UDM failure semantics

> summary: Read when HSS_UNREACHABLE, UDM_UNREACHABLE or SUBSCRIBER_DATA_TIMEOUT appears, to see which procedures depend on the named function.

- 5G registration: the AMF obtains authentication through the AUSF, which uses the UDM. The AMF then registers with the UDM and reads subscription data over N8.
- 4G attach: the MME obtains authentication information and performs update-location with the HSS over S6a.
- IMS registration: the CSCFs query the HSS over Cx.
- An unreachable subscriber-data function mainly affects procedures that need it: new registrations, attaches and re-authentications. How long already-registered devices are unaffected depends on vendor behaviour and timers.
- Several consumers failing against one function supports a function hypothesis. A single consumer failing supports a path hypothesis (SOP-02.1, SOP-02.2).
- A UDM fault and a UDR fault can produce similar symptoms at consumers. Check whether UDM–UDR (N35) observations are available before naming either.

## [REF-CORE.6] Discovery and communication models

> summary: Read when several network functions appear unreachable at once and no single function looks unhealthy.

- Network functions register with the NRF, and consumers use the NRF to discover producers.
- Discovery through the NRF does not mean requests travel through the NRF.
- Requests then travel either directly from consumer to producer, or indirectly via an SCP, depending on the deployment's communication model (TS 23.501 Annex E).
- Possible shared-dependency explanations:
  - an NRF fault (discovery fails);
  - an SCP fault (indirect requests fail);
  - a shared transport segment between core sites (see [REF-TX.1] for mappings).
- The demo topology records `communication_model` (`direct` | `indirect_scp`) for each consumer.

**Baseline function dependencies (Albion Mobile demo, topo-1):**

| Consumer | Depends on | Interface | Communication model |
|---|---|---|---|
| SMF-01, SMF-02, SMF-03 | PCF-02 | N7 | direct |
| AMF-01, AMF-02 | UDM-01 | N8 | direct |
| AUSF-01 | UDM-01 | N13 | direct |
| UDM-01 | UDR-01 | N35 | direct |
| MME-01 | HSS-01 | S6a | direct |
| CSCF-01 | HSS-01 | Cx | direct |

Used by SOP-01.4 and SOP-02.4 to decide whether a shared dependency (one PCF, one UDM, one HSS) covers all the affected consumers, or whether failures are confined to a single consumer's path.

**Service map (Albion Mobile demo):**

| Service | Voice service | Policy function | Interface | Subscriber function |
|---|---|---|---|---|
| VONR-SVC | VoNR | PCF | N5/N7 | — |
| REG-5GS | — | — | — | UDM-01 |

Used by SOP-01.T to confirm a voice-setup-failure trigger actually maps to PCF/N5-N7 before selecting SOP-01 ([REF-CORE.3]).

## [REF-CORE.7] N4 / PFCP failures

> summary: Read when PFCP path failures appear, possibly alongside GTP-C alarms.

- N4 carries PFCP between the SMF and the UPF.
- An N4/PFCP failure can disrupt session establishment or modification through the affected UPF. Whether setup actually fails depends on alternate-UPF selection and recovery behaviour.
- Concurrent GTP-C path failures need their own endpoint, interface and topology checks. GTP-C uses different interfaces and may involve a combined SMF/PGW-C deployment.
- An N4 failure alone does not explain why a GTP-C peer became unreachable. A shared transport fault may explain both (see [REF-CORR.1]).

## [REF-CORE.8] Normalized triggers used by this domain

> summary: Read to confirm what a normalized core trigger means.

| Trigger | Meaning |
|---|---|
| N7_TIMEOUT | SMF policy request to PCF not answered in time |
| PCF_POLICY_REQUEST_FAILURE | PCF returned an error to a policy request |
| PCF_UNREACHABLE | PCF not reachable from a consumer |
| VOLTE_SETUP_FAILURE_RISE | Voice setup failure rate rose above baseline; the voice service, policy function and interface must be identified ([REF-CORE.3]) |
| HSS_UNREACHABLE / UDM_UNREACHABLE | Named subscriber-data function not reachable |
| SUBSCRIBER_DATA_TIMEOUT | Subscriber-data request not answered in time |

## [REF-CORE.9] Evidence the core checks need

> summary: Read to judge whether a core step can be run or must be recorded as unable_to_check.

- Function IDs (SMF, PCF, PCRF, UDM, UDR, HSS, AMF, MME, NRF, SCP), and the topology version valid at incident time.
- Per-consumer operation outcomes in each window: operation name, success, failure and timeout counts, with denominators.
- Error and cause codes as reported, plus the reporting element.
- Function health observations and consumer-to-function reachability observations, with timestamps.
- `failure_handling` per SMF, and `communication_model` per consumer.
- Service map entries for voice: voice service, policy function and interface.
- Change records, with executed-change status and execution time.
- Policy results per PCF–SMF pair in 5-minute buckets, for the SOP-01 persistence check ([RULES.3]).
- Event quality fields: event_id, event_time, ingest_time ([RULES.2], [RULES.4]).
