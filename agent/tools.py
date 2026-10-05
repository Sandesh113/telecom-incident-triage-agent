"""Eight bounded tools. The run/incident scope is fixed by application code."""
import threading
import time

from evidence.contract import Incident, Window, utc
from store import ReadOnlyStore


class ToolBudgetExceeded(RuntimeError):
    pass


class InvestigationTools:
    def __init__(self, store, knowledge, run_id, incident_id, budget=40):
        self.store = ReadOnlyStore(store)
        self.knowledge = knowledge
        self.run_id = run_id
        record = self.store.get(run_id, "incidents", incident_id)
        if record is None:
            raise ValueError("incident not found in this run")
        self.incident = Incident.model_validate(record)
        if self.incident.status != "ready":
            raise ValueError("incident evidence load is incomplete")
        self.trace = []
        self.proposals = []
        self.budget = budget
        self.calls = 0
        self._lock = threading.Lock()

    def _call(self, name, arguments, work):
        with self._lock:
            self.calls += 1
            if self.calls > self.budget:
                raise ToolBudgetExceeded("40-call investigation budget exhausted")
        start = time.monotonic()
        try:
            result = work()
        except Exception as exc:
            self.trace.append({"tool": name, "arguments": arguments, "latency_ms": (time.monotonic()-start)*1000,
                               "error": type(exc).__name__, "evidence_ids": []})
            raise
        self.trace.append({"tool": name, "arguments": arguments, "latency_ms": (time.monotonic()-start)*1000,
                           "evidence_ids": result.get("evidence_ids", []),
                           "availability": result.get("availability")})
        return result

    def rows(self, collection):
        return self.store.query(self.run_id, collection)

    def _result(self, rows, complete=False):
        return {"records": rows, "evidence_ids": [r.get("event_id") or r["evidence_id"] for r in rows],
                "availability": "available" if rows else "known_empty" if complete else "unavailable"}

    def window(self, window):
        return Window.model_validate(window) if window else self.incident.window

    def complete(self, collection, window):
        """Completeness flags cover the incident window, not arbitrary wider queries."""
        bounds = self.incident.window
        return (self.incident.evidence_complete.get(collection, False) and
                utc(bounds.start) <= utc(window.start) and utc(window.end) <= utc(bounds.end))

    @staticmethod
    def within(time_value, window):
        return utc(window.start) <= utc(time_value) < utc(window.end)

    def list_sections(self, doc_id=None):
        return self._call("list_sections", {"doc_id": doc_id}, lambda: {
            "sections": self.knowledge.list_sections(doc_id), "evidence_ids": []})

    def read_section(self, node_id):
        return self._call("read_section", {"node_id": node_id}, lambda: {
            "markdown": self.knowledge.read_section(node_id), "evidence_ids": [node_id]})

    def get_incident_events(self, incident_id, filters=None):
        def work():
            if incident_id != self.incident.incident_id:
                raise ValueError("cross-incident access refused")
            rows = self.rows("events_normalized")
            if filters:
                if set(filters) - {"event_type", "target_object_id", "routing_role"}:
                    raise ValueError("unsupported event filter")
                rows = [r for r in rows if all(r.get(k) == v for k, v in filters.items())]
            return {**self._result(sorted(rows, key=lambda r: utc(r["event_time"])),
                                  self.incident.evidence_complete.get("events_normalized", False)),
                    "incident": self.incident.model_dump(mode="json"),
                    "observations": self.rows("observations"),
                    "evidence_ids": [r["event_id"] for r in rows] + [r["evidence_id"] for r in self.rows("observations")]}
        return self._call("get_incident_events", {"incident_id": incident_id, "filters": filters}, work)

    def get_kpis(self, object_id, kpi=None, windows=None):
        def work():
            rows = [r for r in self.rows("kpi_windows") if r["object_id"] == object_id and (not kpi or r["kpi"] == kpi)]
            if windows:
                requested = [Window.model_validate(w) for w in windows]
                rows = [r for r in rows if any(utc(r["window"]["start"]) == utc(w.start) and
                                              utc(r["window"]["end"]) == utc(w.end) for w in requested)]
            output = [{**r, "failure_rate_pct": 100*r["failures"]/r["attempts"] if r["attempts"] else None,
                       "adequate_samples": r["attempts"] >= 20} for r in rows]
            observations = [r for r in self.rows("observations") if r["object_id"] == object_id]
            return {**self._result(output + observations), "records": output, "observations": observations}
        return self._call("get_kpis", {"object_id": object_id, "kpi": kpi, "windows": windows}, work)

    def get_changes(self, object_ids, window=None):
        def work():
            w = self.window(window)
            rows = [r for r in self.rows("changes") if r["object_id"] in object_ids and self.within(r["event_time"], w)]
            return self._result(rows, self.complete("changes", w))
        return self._call("get_changes", {"object_ids": object_ids, "window": window}, work)

    def get_link_events(self, object_id, window=None):
        def work():
            w = self.window(window)
            rows = [r for r in self.rows("events_normalized") if r["target_object_id"] == object_id and
                    r.get("resulting_state") and self.within(r["event_time"], w)]
            prior = [r for r in self.rows("observations") if r["object_id"] == object_id and
                     r["kind"] == "link_state" and utc(r["event_time"]) < utc(w.start)]
            initial = max(prior, key=lambda r: utc(r["event_time"])) if prior else None
            state = initial["values"]["state"] if initial else None
            transitions = []
            unique = {r["event_id"]: r for r in rows}
            for r in sorted(unique.values(), key=lambda r: (utc(r["event_time"]), r["event_id"])):
                if r.get("transition_duplicate_of"):
                    continue
                if state is not None and state != r["resulting_state"]:
                    transitions.append(r["event_id"])
                state = r["resulting_state"]
            incomplete = "transition_observability_incomplete" in self.incident.flags or any(
                "transition_observability_incomplete" in r.get("flags", []) for r in rows)
            return {**self._result(rows + ([initial] if initial else [])), "records": rows,
                    "initial_state": initial, "transitions_counted": None if incomplete else len(transitions),
                    "transition_event_ids": transitions, "observability_incomplete": incomplete,
                    "initial_state_unknown": initial is None}
        return self._call("get_link_events", {"object_id": object_id, "window": window}, work)

    def get_customer_impact(self, incident_id, window=None):
        def work():
            if incident_id != self.incident.incident_id:
                raise ValueError("cross-incident access refused")
            w = self.window(window)
            rows = [r for r in self.rows("impact_records") if self.within(r["event_time"], w)]
            complete = self.complete("impact_records", w)
            customers = sorted({r["customer_id"] for r in rows})
            enterprises = sorted({r["enterprise_id"] for r in rows if r.get("enterprise_id")})
            level = ("severe" if len(customers) >= 500 or len(enterprises) >= 2 else
                     "significant" if len(customers) >= 100 or enterprises else "below_tiers") if complete else "impact_tier_unknown"
            return {**self._result(rows, complete), "window_start": w.start, "window_end": w.end,
                    "customer_ids": customers, "enterprise_ids": enterprises,
                    "distinct_customers": len(customers) if complete else None,
                    "distinct_enterprise_customers": len(enterprises) if complete else None, "level": level}
        return self._call("get_customer_impact", {"incident_id": incident_id, "window": window}, work)

    def propose_action(self, description, type, target):
        def work():
            if type not in ("read_only", "change"):
                raise ValueError("unknown action type")
            proposal = {"description": description, "type": type, "target_object": target,
                        "requires_approval": type == "change"}
            self.proposals.append(proposal)
            return {"proposal": proposal, "executed": False, "evidence_ids": []}
        return self._call("propose_action", {"description": description, "type": type, "target": target}, work)

    def strand_tools(self):
        """Explicit allowlist; no default filesystem, shell or network tools."""
        from strands import tool
        @tool
        def list_sections(doc_id: str | None = None) -> dict:
            """List knowledge node IDs, titles and summaries, optionally for one document."""
            return self.list_sections(doc_id)
        @tool
        def read_section(node_id: str) -> dict:
            """Read exactly one SOP/rule/reference section by ID. Includes citation ID."""
            return self.read_section(node_id)
        @tool
        def get_incident_events(incident_id: str, filters: dict | None = None) -> dict:
            """Read enriched events, incident metadata and observations. Never normalizes raw alarms."""
            return self.get_incident_events(incident_id, filters)
        @tool
        def get_kpis(object_id: str, kpi: str | None = None, windows: list[dict] | None = None) -> dict:
            """Read KPI counts/rates and object observations. Omit windows to read baseline and incident windows."""
            return self.get_kpis(object_id, kpi, windows)
        @tool
        def get_changes(object_ids: list[str], window: dict | None = None) -> dict:
            """Read changes for objects in a half-open start/end UTC window; distinguish unavailable from known empty."""
            return self.get_changes(object_ids, window)
        @tool
        def get_link_events(object_id: str, window: dict | None = None) -> dict:
            """Read link states and pre-window snapshot; count state transitions deterministically."""
            return self.get_link_events(object_id, window)
        @tool
        def get_customer_impact(incident_id: str, window: dict | None = None) -> dict:
            """Read impact evidence and compute distinct customers/enterprises and tier for a 15-minute window."""
            return self.get_customer_impact(incident_id, window)
        @tool
        def propose_action(description: str, type: str, target: str) -> dict:
            """Add a draft action only; change proposals require approval. Never executes or sends anything."""
            return self.propose_action(description, type, target)
        return [list_sections, read_section, get_incident_events, get_kpis, get_changes,
                get_link_events, get_customer_impact, propose_action]
