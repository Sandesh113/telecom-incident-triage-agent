"""The SKILL.md output contract; domain enums are intentionally closed."""
from typing import Literal

from pydantic import Field

from evidence.contract import StrictModel

Mechanism = Literal["pcf_service_fault", "smf_pcf_path_fault", "core_shared_dependency", "udm_function_fault",
                    "udr_fault", "consumer_path_fault", "transport_link_flap", "rf_interference", "rf_pci_collision",
                    "rf_missing_neighbour_or_measurement_config"]


class AddedSOP(StrictModel):
    sop_id: str
    reason: str


class Routing(StrictModel):
    triggers: list[str]
    triggered_sops: list[str]
    added_sops: list[AddedSOP]
    context_event_ids: list[str]
    flags: list[str]
    routing_gap: bool


class Hypothesis(StrictModel):
    hypothesis_id: str
    cause_object: str
    mechanism: Mechanism
    cause: str
    status: Literal["candidate", "supported", "weakened"]
    supporting_event_ids: list[str]
    conflicting_event_ids: list[str]
    knowledge_ids: list[str]


class Assessment(StrictModel):
    hypothesis_id: str
    result: Literal["supports", "weakens", "inconclusive", "unable_to_check"]
    explanation: str


class SOPStep(StrictModel):
    step_id: str
    observation: str
    event_ids: list[str]
    metrics: dict
    outcome: Literal["continuing_flap", "below_continuing_flap_threshold", "unable_to_check"] | None
    missing_fields: list[str]
    assessments: list[Assessment]


class Control(StrictModel):
    object_id: str
    qualified_by: list[str]


class Attribution(StrictModel):
    object_id: str
    state: Literal["single", "multiple", "unresolved", "unexplained"]
    hypothesis_ids: list[str]
    event_ids: list[str]


class Impact(StrictModel):
    window_start: str
    window_end: str
    distinct_customers: int | None = Field(ge=0)
    distinct_enterprise_customers: int | None = Field(ge=0)
    level: Literal["severe", "significant", "below_tiers", "impact_tier_unknown"]


class Escalation(StrictModel):
    required: bool
    reasons: list[str]
    rule_ids: list[str]


class Action(StrictModel):
    description: str
    target_object: str
    type: Literal["read_only", "change"]
    requires_approval: bool


class Report(StrictModel):
    report_version: int = Field(ge=1)
    supersedes: int | None
    late_events: list[str]
    affected_objects: list[str]
    routing: Routing
    hypotheses: list[Hypothesis]
    sop_steps: list[SOPStep]
    controls_used: list[Control]
    unexplained_objects: list[str]
    attribution: list[Attribution]
    impact: Impact
    escalation: Escalation
    proposed_actions: list[Action]
