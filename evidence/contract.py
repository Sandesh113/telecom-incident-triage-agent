"""Contract between enrichment/loader and the agent. All windows are half-open."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamps must have a UTC offset")
    return parsed


class Window(StrictModel):
    start: str
    end: str

    @model_validator(mode="after")
    def ordered(self):
        if utc(self.start) >= utc(self.end):
            raise ValueError("window must have start < end")
        return self


class Event(StrictModel):
    event_id: str = Field(min_length=1, pattern=r"^[^#]+$")
    event_time: str
    ingest_time: str
    source_system: str
    event_type: str
    reporting_object_id: str
    target_object_id: str
    target_object_type: str
    routing_trigger: str | None = None
    routing_role: Literal["route", "context"]
    alarm_state: Literal["active", "cleared"] | None = None
    resulting_state: Literal["up", "down"] | None = None
    transition_duplicate_of: str | None = None
    late_event: bool = False
    flags: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_times(self):
        delta = utc(self.ingest_time) - utc(self.event_time)
        if delta < timedelta(0):
            raise ValueError("ingest_time precedes event_time")
        if self.late_event != (delta > timedelta(minutes=5)):
            raise ValueError("late_event must reflect ingest minus event time")
        if self.routing_role == "route" and not self.routing_trigger:
            raise ValueError("a routed event requires a normalized trigger")
        return self


class Observation(StrictModel):
    evidence_id: str = Field(min_length=1, pattern=r"^[^#]+$")
    object_id: str
    event_time: str
    kind: str
    values: dict


class KPI(StrictModel):
    evidence_id: str = Field(min_length=1, pattern=r"^[^#]+$")
    object_id: str
    kpi: str
    window: Window
    attempts: int = Field(ge=0)
    failures: int = Field(ge=0)

    @model_validator(mode="after")
    def counts(self):
        if self.failures > self.attempts:
            raise ValueError("failures exceed attempts")
        return self


class Change(StrictModel):
    evidence_id: str = Field(min_length=1, pattern=r"^[^#]+$")
    object_id: str
    event_time: str
    status: Literal["executed", "planned", "cancelled"]
    description: str


class Impact(StrictModel):
    evidence_id: str = Field(min_length=1, pattern=r"^[^#]+$")
    customer_id: str
    enterprise_id: str | None = None
    object_id: str
    event_time: str


class Incident(StrictModel):
    incident_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    run_id: UUID
    window: Window
    affected_objects: list[str] = Field(min_length=1)
    synthetic: bool
    flags: list[str] = Field(default_factory=list)
    evidence_complete: dict[str, bool] = Field(default_factory=dict)
    status: Literal["ready", "loading"] = "ready"
    contract_version: Literal["1"] = "1"


class Bundle(StrictModel):
    incident: Incident
    events_normalized: list[Event]
    observations: list[Observation] = Field(default_factory=list)
    kpi_windows: list[KPI] = Field(default_factory=list)
    changes: list[Change] = Field(default_factory=list)
    impact_records: list[Impact] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence(self):
        seen = set()
        for collection in (self.events_normalized, self.observations, self.kpi_windows,
                           self.changes, self.impact_records):
            for record in collection:
                key = getattr(record, "event_id", None) or record.evidence_id
                if key in seen:
                    raise ValueError(f"duplicate evidence ID: {key}")
                seen.add(key)
                if hasattr(record, "event_time"):
                    utc(record.event_time)
        if len(set(self.incident.affected_objects)) != len(self.incident.affected_objects):
            raise ValueError("duplicate affected object")
        return self


def ready_event(incident: Incident) -> dict:
    """An event descriptor, not an AWS API call. Publish only after loading succeeds."""
    return {"Source": "sop-rca.enrichment", "DetailType": "incident.ready",
            "Detail": {"contract_version": "1", "incident_id": incident.incident_id,
                       "run_id": str(incident.run_id), "previous_report_key": None}}
