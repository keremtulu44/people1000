"""Standard-library reference engine. Time is integer simulation minutes.

Only the engine mutates reality. A provider receives a detached, local observation
and proposes an action; it never receives engine access or authoritative globals.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import heapq
import json
from pathlib import Path
import random
from typing import Protocol

from . import dynamics, collective, characters, agenda, psychology
from .behavior import load_profile, sample_traits, validate_profile

GROUPS = {name: group["population_percent"] for name, group in load_profile()["groups"].items()}
VERSION = 2


@dataclass
class Config:
    population: int = 100
    seed: int = 44
    read_budget: int = 6
    communication_budget: int = 2
    action_budget: int = 3
    cumulative_enabled: bool = True
    ablation: str = "none"

    def __post_init__(self):
        if self.ablation not in ("none", "economic_evidence", "peer", "trust_erosion"):
            raise ValueError("Unknown diagnostic ablation")
        if type(self.cumulative_enabled) is not bool:
            raise ValueError("cumulative_enabled must be boolean")
        if type(self.seed) is not int:
            raise ValueError("Seed must be an integer")
        if type(self.population) is not int or self.population < 100 or self.population % 100:
            raise ValueError("Population must be a positive multiple of 100")
        if any(type(v) is not int or v < 0 for v in (self.read_budget, self.communication_budget, self.action_budget)):
            raise ValueError("Budgets cannot be negative")


@dataclass
class Agent:
    id: str
    initial_group: str
    alignment: str
    savings: float
    income: float
    expense: float
    traits: dict
    initial_traits: dict
    permissions: list = field(default_factory=list)
    employer: str | None = None
    authority_dependency: str | None = None
    public_support: float = 0.5
    private_loyalty: float = 0.5
    beliefs: dict = field(default_factory=dict)
    memories: list = field(default_factory=list)
    inbox: list = field(default_factory=list)
    used: dict = field(default_factory=lambda: {"read": 0, "communication": 0, "action": 0})
    budget_day: int = 0
    behavior: dict = field(default_factory=dict)
    public_alignment: str = "none"
    pressure: float = 0.0
    change_evidence: float = 0.0
    losses: float = 0.0


class DecisionProvider(Protocol):
    def decide(self, observation: dict) -> dict: ...


class BaselineProvider:
    """Deliberately simple, deterministic comparison policy; not a full AI model."""
    def decide(self, observation: dict) -> dict:
        ordinary=agenda.policy(observation)
        if ordinary is not None:return ordinary
        proposal, reason = characters.policy(observation)
        if "character" in observation:
            return proposal or {"type":"wait"}
        if proposal is None:
            proposal = collective.policy(observation)
        if proposal is not None:
            return proposal
        messages = [m for m in observation["messages"] if "message_id" in m]
        if messages and observation["contacts"]:
            return {"type": "relay", "message_id": messages[-1]["message_id"],
                    "target": observation["contacts"][0]}
        return {"type": "wait"}


class Simulation:
    def __init__(self, config: Config | None = None, behavior_profile: dict | None = None):
        self.config = config or Config()
        self.behavior_profile = validate_profile(behavior_profile) if behavior_profile is not None else load_profile()
        self.rng = random.Random(self.config.seed)
        self.time = 0
        self.seq = 0
        self.queue = []
        self.processed = set()
        self.log = []
        self.decisions = []
        self.agents = {}
        self.edges = []
        self.authorities = {}
        self.messages = {}
        if collective.enabled(self):
            self.gatherings = {}
        self.calls = []
        self.last_daily_day = -1
        self.price = 1.0
        self.pole_power = {"A": 80.0, "B": 80.0}
        # Frozen protocol accompanies every saved experiment.
        self.protocol = {"version": VERSION, "config": asdict(self.config),
                         "behavior_profile": deepcopy(self.behavior_profile),
                         "metrics": ["reach", "delivery_latency", "support_gap", "alignment_changes",
                                     "economic_losses", "perception_error", "rejected_actions"],
                         "failure_conditions": ["unreachable delivery", "unauthorized mutation",
                                                "duplicate application", "budget overflow"],
                         "limitations": ["uncalibrated traits", "baseline policy is not an AI",
                                         "uncalibrated cumulative dynamics", "no realism claim"]}
        self.daily_metrics = []
        self.experiment_id = "local"
        self._populate()
        if characters.enabled(self):
            characters.prepare_network(self)
        self._initialize_behavior()
        if collective.enabled(self):
            for a in self.agents.values():
                collective.state(a)
        if characters.enabled(self):
            characters.initialize(self)
        if agenda.enabled(self):agenda.initialize(self)
        if psychology.enabled(self):
            psychology.initialize(self)
        self.schedule(0, "daily", {})

    def _id(self, prefix):
        self.seq += 1
        return f"{prefix}{self.seq:08d}"

    def _populate(self):
        psych_on = psychology.enabled(self)
        for group, settings in self.behavior_profile["groups"].items():
            fraction = settings["population_percent"]
            count = self.config.population * fraction // 100
            for idx in range(count):
                aid = f"A{len(self.agents) + 1:04d}"
                subwing = None
                if psych_on and group == "wealthy":
                    subwing = psychology.wealthy_subwing(idx)
                    pole = psychology.pole_for_wealthy_subwing(subwing)
                else:
                    pole = "B" if group == "opposition" else (
                        "none" if group in {"observer", "discontented"} else self.rng.choice(["A", "B"]))
                    if group == "power_aligned":
                        pole = "A"
                traits = sample_traits(self.rng, settings, subwing=subwing)
                is_wealthy = group in {"wealthy", "authority"}
                perms = ["pressure", "revoke_contract"] if group == "authority" else (
                    ["amplify"] if psych_on and group == "wealthy" else [])
                self.agents[aid] = Agent(aid, group, pole,
                    self.rng.uniform(200, 400) if is_wealthy else self.rng.uniform(20, 80),
                    15.0 if is_wealthy else 5.0, 4.0, traits, deepcopy(traits), perms)
        leaders = [a.id for a in self.agents.values() if a.initial_group == "authority"]
        leaders_a = [x for x in leaders if self.agents[x].alignment == "A"] or leaders
        leaders_b = [x for x in leaders if self.agents[x].alignment == "B"] or leaders
        wealthy = [a.id for a in self.agents.values() if a.initial_group == "wealthy"]
        for leader in leaders:
            a = self.agents[leader]
            self.authorities[leader] = {"pole_alignment": a.alignment, "institutional_power": 1.0,
                "allied_authorities": [x for x in leaders if x != leader and self.agents[x].alignment == a.alignment],
                "conflicting_authorities": [x for x in leaders if self.agents[x].alignment != a.alignment]}
        ids = list(self.agents)
        if not psych_on:
            for a in self.agents.values():
                degree = 1 if a.initial_group == "observer" else (3 if a.initial_group == "discontented" else 5)
                for target in self.rng.sample([x for x in ids if x != a.id], degree):
                    self.edges.append({"source": a.id, "target": target, "type": "close",
                                       "trust": self.rng.uniform(.3, .9), "latency": self.rng.randint(15, 180)})
                if a.initial_group != "observer":
                    matches = [x for x in leaders if self.agents[x].alignment == a.alignment]
                    leader = self.rng.choice(matches or leaders)
                    if not self.edge(leader, a.id) and leader != a.id:
                        self.edges.append({"source": leader, "target": a.id, "type": "authority",
                                           "trust": self.rng.uniform(.6, .95), "latency": self.rng.randint(5, 90)})
                if a.initial_group == "wealthy":
                    a.authority_dependency = self.rng.choice(leaders)
                if a.initial_group not in {"wealthy", "authority"}:
                    a.employer = self.rng.choice(wealthy)
        else:
            # v3.4: Yankı odaları (homophily), sosyal medya yayın erişimi ve gözlemci izleme ağları
            wealthy_idx_map = {wid: idx for idx, wid in enumerate(wealthy)}
            for a in self.agents.values():
                others = [x for x in ids if x != a.id and self.agents[x].initial_group != "observer"]
                if a.initial_group in ("power_aligned", "opposition"):
                    same_pole = [x for x in others if self.agents[x].alignment == a.alignment]
                    diff_pole = [x for x in others if self.agents[x].alignment != a.alignment]
                    in_picks = self.rng.sample(same_pole, min(4, len(same_pole)))
                    out_picks = self.rng.sample(diff_pole, min(1, len(diff_pole)))
                    for target in in_picks:
                        self.edges.append({"source": a.id, "target": target, "type": "close",
                                           "trust": self.rng.uniform(.58, .92), "latency": self.rng.randint(15, 120)})
                    for target in out_picks:
                        self.edges.append({"source": a.id, "target": target, "type": "close",
                                           "trust": self.rng.uniform(.25, .52), "latency": self.rng.randint(45, 180)})
                elif a.initial_group == "discontented":
                    solidarity = [x for x in others if self.agents[x].initial_group in ("discontented", "opposition")]
                    rest = [x for x in others if x not in solidarity]
                    for target in self.rng.sample(solidarity, min(2, len(solidarity))):
                        self.edges.append({"source": a.id, "target": target, "type": "close",
                                           "trust": self.rng.uniform(.55, .88), "latency": self.rng.randint(15, 120)})
                    for target in self.rng.sample(rest, min(1, len(rest))):
                        self.edges.append({"source": a.id, "target": target, "type": "close",
                                           "trust": self.rng.uniform(.30, .60), "latency": self.rng.randint(30, 180)})
                elif a.initial_group == "observer":
                    # Gözlemci dışarıya az konuşur (1 bağ), ama iki kutbu ve medyayı dengeli izler (6 gelen bağ)
                    target = self.rng.choice(others)
                    self.edges.append({"source": a.id, "target": target, "type": "close",
                                       "trust": self.rng.uniform(.35, .60), "latency": self.rng.randint(30, 150)})
                    pro_a_w = [w for w in wealthy if psychology.wealthy_subwing(wealthy_idx_map[w]) == "pro_A"]
                    pro_b_w = [w for w in wealthy if psychology.wealthy_subwing(wealthy_idx_map[w]) == "pro_B"]
                    citizens_a = [x for x in others if self.agents[x].initial_group == "power_aligned"]
                    citizens_b = [x for x in others if self.agents[x].initial_group in ("opposition", "discontented")]
                    monitors = [
                        self.rng.choice(leaders_a),
                        self.rng.choice(leaders_b),
                        self.rng.choice(pro_a_w or wealthy),
                        self.rng.choice(pro_b_w or wealthy),
                        self.rng.choice(citizens_a or others),
                        self.rng.choice(citizens_b or others),
                    ]
                    for src in dict.fromkeys(monitors):
                        if src != a.id and not self.edge(src, a.id):
                            self.edges.append({"source": src, "target": a.id, "type": "monitor",
                                               "trust": self.rng.uniform(.40, .60), "latency": self.rng.randint(10, 60)})
                else:
                    for target in self.rng.sample(others, min(5, len(others))):
                        self.edges.append({"source": a.id, "target": target, "type": "close",
                                           "trust": self.rng.uniform(.40, .85), "latency": self.rng.randint(15, 150)})

                if a.initial_group != "observer":
                    matches = [x for x in leaders if self.agents[x].alignment == a.alignment]
                    leader = self.rng.choice(matches or leaders)
                    if not self.edge(leader, a.id) and leader != a.id:
                        self.edges.append({"source": leader, "target": a.id, "type": "authority",
                                           "trust": self.rng.uniform(.6, .95), "latency": self.rng.randint(5, 90)})

                if a.initial_group == "wealthy":
                    sw = psychology.wealthy_subwing(wealthy_idx_map[a.id])
                    # İktidar ve düzen sopası: A yanlısı ve Tarafsız/Ticari sermaye A otoritesine bağımlıdır;
                    # B yanlısı medyanın da düzenleyici olarak yarısı A otoritesi denetimindedir.
                    if sw in ("pro_A", "neutral_commercial"):
                        a.authority_dependency = self.rng.choice(leaders_a)
                    else:
                        a.authority_dependency = self.rng.choice(leaders_a if wealthy_idx_map[a.id] % 2 == 0 else leaders_b)
                    # Sosyal medya etki ekibi yayın ağı (audience / media edges)
                    if sw == "pro_A":
                        pool = [x for x in others if x != a.id and self.agents[x].initial_group in ("power_aligned", "discontented", "wealthy")]
                    elif sw == "pro_B":
                        pool = [x for x in others if x != a.id and self.agents[x].initial_group in ("opposition", "discontented", "wealthy")]
                    else:
                        pool = [x for x in others if x != a.id]
                    for follower in self.rng.sample(pool, min(12, len(pool))):
                        if not self.edge(a.id, follower):
                            trust_lo, trust_hi = (.50, .82) if self.agents[follower].alignment == a.alignment and a.alignment in ("A", "B") else (.28, .58)
                            self.edges.append({"source": a.id, "target": follower, "type": "media",
                                               "trust": self.rng.uniform(trust_lo, trust_hi), "latency": self.rng.randint(5, 45)})

                if a.initial_group not in {"wealthy", "authority"}:
                    if a.initial_group == "power_aligned":
                        pref = [w for w in wealthy if psychology.wealthy_subwing(wealthy_idx_map[w]) in ("pro_A", "neutral_commercial")]
                    elif a.initial_group == "opposition":
                        pref = [w for w in wealthy if psychology.wealthy_subwing(wealthy_idx_map[w]) in ("pro_B", "neutral_commercial")]
                    else:
                        pref = wealthy
                    a.employer = self.rng.choice(pref or wealthy)

    def _initialize_behavior(self):
        wealthy_idx = 0
        psych_on = psychology.enabled(self)
        for a in self.agents.values():
            subwing = None
            if psych_on and a.initial_group == "wealthy":
                subwing = psychology.wealthy_subwing(wealthy_idx)
                wealthy_idx += 1
            if a.behavior:
                if subwing and "subwing" not in a.behavior:
                    a.behavior["subwing"] = subwing
                continue
            known = {}
            # Initial public affiliations of directly connected people are part of
            # the initial local world, not access to their private loyalty.
            for edge in self.edges:
                if edge["source"] == a.id or edge["target"] == a.id:
                    other = edge["target"] if edge["source"] == a.id else edge["source"]
                    person = self.agents[other]
                    known[other] = {"pole": person.public_alignment if person.public_alignment != "none" else person.alignment,
                                    "group": person.initial_group, "trust": edge["trust"]}
            dynamics.initialize(a, known)
            if subwing:
                a.behavior["subwing"] = subwing
            if a.public_alignment == "none":
                a.public_alignment = a.alignment

    def edge(self, source, target):
        return next((e for e in self.edges if e["source"] == source and e["target"] == target), None)

    def schedule(self, time: int, kind: str, payload: dict, caused_by=None):
        if type(time) is not int or time < self.time:
            raise ValueError("Events need an integer time not earlier than now")
        self._validate_event(time, kind, payload)
        eid = self._id("E")
        heapq.heappush(self.queue, (time, -self.seq if kind == "daily" else self.seq, eid, kind, deepcopy(payload), caused_by))
        return eid

    def _validate_event(self, time, kind, p):
        if not isinstance(kind, str) or not isinstance(p, dict):
            raise ValueError("Invalid event")
        if kind in agenda.EVENTS:
            agenda.validate_event(self,kind,p)
        elif kind == "daily":
            if time % 1440:
                raise ValueError("Daily routines require a day boundary")
        elif kind == "price_shock":
            if type(p.get("multiplier")) not in (int, float) or not 0 < p["multiplier"] <= 10:
                raise ValueError("Invalid price multiplier")
        elif kind == "local_disruption":
            if (not characters.enabled(self) or not isinstance(p.get("target"),str) or p["target"] not in self.agents
                    or not isinstance(p.get("domain"),str) or not 0<len(p["domain"])<=64
                    or p["domain"] in ("living_cost","income_security")
                    or type(p.get("severity")) not in (int,float) or not 0<=p["severity"]<=1):
                raise ValueError("Invalid direct local disruption")
        elif kind == "power_change":
            if not isinstance(p.get("pole"), str) or p["pole"] not in self.pole_power or type(p.get("value")) not in (int, float) or not 0 <= p["value"] <= 100:
                raise ValueError("Invalid power change")
        elif kind == "external_action":
            if not isinstance(p.get("actor"), str) or p["actor"] not in self.agents or not isinstance(p.get("proposal"), dict):
                raise ValueError("Invalid scheduled intervention")
        elif kind == "gathering_close":
            if not collective.enabled(self) or not isinstance(p.get("gathering_id"), str) or p["gathering_id"] not in self.gatherings:
                raise ValueError("Unknown gathering")
            if time != self.gatherings[p["gathering_id"]]["end"]:
                raise ValueError("Gathering closes at its registered end")
        elif kind == "day_end":
            pass
        elif kind in {"read", "decide", "delivery", "behavior"}:
            if not isinstance(p.get("target"), str) or p["target"] not in self.agents:
                raise ValueError("Unknown event target")
            if kind == "delivery":
                if not isinstance(p.get("sender"), str) or p["sender"] not in self.agents or not isinstance(p.get("message_id"), str) or p["message_id"] not in self.messages:
                    raise ValueError("Invalid delivery source or message")
                scope = self.messages[p["message_id"]].get("audience")
                if scope is not None and p["target"] not in scope:
                    raise ValueError("Delivery outside audience")
                sender = self.agents[p["sender"]]
                message = self.messages[p["message_id"]]
                if not self.edge(sender.id, p["target"]) or (sender.id != message["original_source"] and not any(m.get("message_id") == message["id"] for m in sender.memories)):
                    raise ValueError("Sender has no access to message or target")
        else:
            raise ValueError("Unknown event type")

    @staticmethod
    def _safe_proposal(proposal):
        # Reject non-JSON/non-finite responses without poisoning future snapshots.
        try:
            return json.loads(json.dumps(proposal, allow_nan=False))
        except (TypeError, ValueError, OverflowError):
            return {"invalid_proposal": "non-JSON or non-finite response"}

    def record(self, kind, payload, caused_by=None, event_id=None):
        eid = self._id("L")
        self.log.append({"id": eid, "time": self.time, "kind": kind,
                         "payload": deepcopy(payload), "caused_by": caused_by, "event_id": event_id})
        return eid

    def observation(self, aid):
        """No global power, price, hidden memories or other agents' private state."""
        a = self.agents[aid]
        result = deepcopy({"agent_id": aid, "time": self.time, "group": a.initial_group,
            "traits": a.traits, "alignment": a.alignment, "savings": a.savings,
            "behavior": a.behavior, "private_loyalty": a.private_loyalty, "public_support": a.public_support,
            "beliefs": a.beliefs, "messages": [m for m in a.memories if "message_id" in m][-10:], "experiences": [m for m in a.memories if "message_id" not in m][-10:], "budgets_used": a.used,
            "contacts": [e["target"] for e in self.edges if e["source"] == aid],
            "allowed_actions": ["wait", "send", "relay", "declare_support"] + a.permissions,
            "untrusted_data_fields": ["messages", "beliefs"]})
        if collective.enabled(self):
            result["social"] = collective.observe(self,a)
            result["political_responsibility"] = a.behavior.get("appraisal",{}).get("responsibility_current",0.)
            result["allowed_actions"].extend(collective.ACTIONS)
            result["untrusted_data_fields"].append("social.known_gatherings")
        if characters.enabled(self):
            result["budget_limits"]={"action":self.config.action_budget,
                "read":characters.limit(self,a,"read",self.config.read_budget),
                "communication":characters.limit(self,a,"communication",self.config.communication_budget)}
            result["untrusted_data_fields"].extend(["character.signals","character.grievances"])
            result["character"] = deepcopy(characters.state(a))
            result["character_config"] = deepcopy(self.behavior_profile["character_dynamics"])
            if a.initial_group=="authority":
                result["allowed_actions"].append("compete_position")
                result["institutional_position"]=self.authorities[aid]["institutional_power"]
            if a.initial_group=="observer":result["allowed_actions"].append("self_study")
        if agenda.enabled(self):
            result["agenda"]=deepcopy(agenda.state(a))
            result["allowed_actions"].extend(agenda.ACTIONS)
            result["untrusted_data_fields"].extend(["agenda.claims","agenda.suggestion"])
        if psychology.enabled(self):
            result["psychology"] = deepcopy(psychology.state(a))
        return result

    def propose(self, aid, proposal, cause=None):
        """Explicit proposal boundary; permissions and identity never come from model output."""
        did = self._id("D")
        self.decisions.append({"id": did, "actor": aid, "time": self.time,
                               "proposal": self._safe_proposal(proposal), "cause": cause})
        return did

    def apply(self, did):
        if did in self.processed:
            return False
        d = next((x for x in self.decisions if x["id"] == did), None)
        if d is None:
            raise ValueError("Unknown decision")
        a = self.agents.get(d["actor"])
        p = d["proposal"]
        reason = self._validate(a, p)
        self.processed.add(did)
        if reason:
            self.record("action_rejected", {"decision": did, "reason": reason}, d["cause"])
            return False
        kind = p["type"]
        self._refresh_budget(a)
        if kind != "wait":
            a.used["action"] += 1
        if kind in {"send", "relay"}:
            a.used["communication"] += 1
            if kind == "send":
                mid = self._id("M")
                self.messages[mid] = {"id": mid, "original_source": a.id,
                    "created_at": self.time, "source_group": a.initial_group, "source_alignment": a.public_alignment if collective.enabled(self) else a.alignment, "text": p["text"], "topic": p.get("topic", "general"),
                    "claim": p.get("claim"), "audience": p.get("audience")}
                if p.get("agenda_id") is not None:agenda.attach(self,a,p,self.messages[mid])
                if collective.enabled(self) and p.get("gathering_id") is not None:
                    self.messages[mid]["gathering"] = collective.invitation(self,a,p["gathering_id"])
            else:
                mid = p["message_id"]
            edge = self.edge(a.id, p["target"])
            self.schedule(self.time + edge["latency"], "delivery",
                          {"message_id": mid, "sender": a.id, "target": p["target"]}, did)
        elif kind == "amplify":
            a.used["communication"] += 1
            if "message_id" in p and p["message_id"] is not None:
                mid = p["message_id"]
            else:
                mid = self._id("M")
                self.messages[mid] = {
                    "id": mid, "original_source": a.id, "created_at": self.time,
                    "source_group": a.initial_group,
                    "source_alignment": a.public_alignment if collective.enabled(self) else a.alignment,
                    "text": p["text"], "topic": p.get("topic", "general"),
                    "claim": p.get("claim"), "audience": None,
                }
            media_edges = [e for e in self.edges if e["source"] == a.id and e["type"] == "media"]
            close_edges = [e for e in self.edges if e["source"] == a.id and e["type"] != "media"]
            chosen_edges = (media_edges + close_edges)[:12]
            scope = self.messages[mid].get("audience")
            delivered_targets = []
            for edge in chosen_edges:
                tgt = edge["target"]
                if scope is not None and tgt not in scope:
                    continue
                delivered_targets.append(tgt)
                self.schedule(self.time + edge["latency"], "delivery",
                              {"message_id": mid, "sender": a.id, "target": tgt}, did)
            self.record("media_amplified", {"actor": a.id, "message_id": mid,
                                            "subwing": a.behavior.get("subwing"),
                                            "reach_count": len(delivered_targets)}, did)
        elif kind in agenda.ACTIONS:
            agenda.apply(self,a,p,did)
        elif kind in characters.ACTIONS:
            characters.apply(self,a,p,did)
        elif kind in collective.ACTIONS:
            collective.apply(self,a,p,did)
        elif kind == "declare_support":
            a.public_support = p["value"]
            a.public_alignment = a.alignment
        elif kind == "pressure":
            a.savings -= 2
            target = self.agents[p["target"]]
            target.public_alignment = a.alignment
            target.pressure = min(1.0, target.pressure + .2)
            # Limited direct economic/self-reported experience, not a global broadcast.
            target.public_support = min(1., target.public_support + target.traits["pressure_response"])
            a.public_support = max(0., a.public_support - .02)
            target.memories.append({"event_id": did, "learned_at": self.time, "type": "direct_experience", "actor": a.id, "pressure": .2})
            self.record("pressure_experienced", {"target": target.id, "actor": a.id}, did)
            if psychology.enabled(self):
                psychology.apply_stimulus(self, target, "pressure", 0.5, did)
                if target.initial_group == "wealthy":
                    ec = target.behavior.setdefault("economic_chain", {"contract_factor": 1.0, "boycott_penalty": 0.0, "employer_cut": 0.0})
                    ec["contract_factor"] = max(0.65, ec["contract_factor"] - 0.12)
        elif kind == "revoke_contract":
            a.savings -= 2
            target = self.agents[p["target"]]
            capacity=min(1.,self.authorities[a.id]["institutional_power"]) if characters.enabled(self) else 1.
            loss = target.income * .3 * capacity
            target.income -= loss
            target.losses += loss
            target.memories.append({"event_id": did, "learned_at": self.time,
                                    "type": "direct_experience", "income_loss": loss})
            from . import appraisal
            if appraisal.enabled(self):
                appraisal.direct_notice(self,target,a.id,a.public_alignment,loss,did)
            if psychology.enabled(self):
                psychology.apply_stimulus(self, target, "contract_loss", min(1.0, loss / max(1.0, target.income + loss)), did)
                if target.initial_group == "wealthy":
                    ec = target.behavior.setdefault("economic_chain", {"contract_factor": 1.0, "boycott_penalty": 0.0, "employer_cut": 0.0})
                    ec["contract_factor"] = max(0.35, ec["contract_factor"] - 0.28)
        if characters.enabled(self):
            local=characters.state(a)
            if kind=="send" and p.get("gathering_id") is not None:
                local["invited"].setdefault(p["gathering_id"],[]).append(p["target"])
            if kind=="send" and p.get("topic")=="grievance":local["last_grievance_day"]=self.time//1440
            if kind=="create_gathering":local["last_gathering_day"]=self.time//1440
            if kind=="create_gathering" or (kind=="send" and p.get("gathering_id") is not None):
                self.schedule(self.time,"decide",{"target":a.id},did)
            if kind=="compete_position":self.schedule(self.time,"decide",{"target":p["target"]},did)
        self.record("action_applied", {"decision": did, "actor": a.id, "type": kind, "target": p.get("target"), "public_support": a.public_support}, d["cause"])
        return True

    def _refresh_budget(self, a):
        day = self.time // 1440
        if a.budget_day != day:
            a.used = {"read": 0, "communication": 0, "action": 0}
            a.budget_day = day

    def _validate(self, a, p):
        if a is None or not isinstance(p, dict):
            return "invalid proposal or actor"
        kind = p.get("type")
        allowed = {"wait", "send", "relay", "declare_support", "pressure", "revoke_contract"}
        if psychology.enabled(self):
            allowed.add("amplify")
        if collective.enabled(self):
            allowed.update(collective.ACTIONS)
        if characters.enabled(self):allowed.update(characters.ACTIONS)
        if agenda.enabled(self):allowed.update(agenda.ACTIONS)
        if not isinstance(kind, str) or kind not in allowed:
            return "unknown action"
        used = a.used if a.budget_day == self.time // 1440 else {"action": 0, "communication": 0}
        if kind != "wait" and used["action"] >= self.config.action_budget:
            return "action budget exhausted"
        if kind in agenda.ACTIONS:return agenda.validate(self,a,p)
        if kind in characters.ACTIONS:return characters.validate(self,a,p)
        if kind in collective.ACTIONS:
            return collective.validate(self,a,p)
        if kind == "amplify":
            if "amplify" not in a.permissions:
                return "permission denied"
            if used["communication"] >= characters.limit(self, a, "communication", self.config.communication_budget):
                return "communication budget exhausted"
            if psychology.enabled(self) and psychology.state(a).get("expression_mode") == "self_censored":
                return "self_censored_under_fear"
            if not any(e["source"] == a.id for e in self.edges):
                return "no communication path"
            if p.get("message_id") is not None:
                mid = p.get("message_id")
                if not isinstance(mid, str) or mid not in self.messages:
                    return "message not learned"
                if not any(m.get("message_id") == mid for m in a.memories):
                    return "message not learned"
            else:
                if not isinstance(p.get("topic", "general"), str) or not 0 < len(p.get("topic", "general")) <= 200:
                    return "invalid topic"
                if not isinstance(p.get("text"), str) or not 0 < len(p["text"]) <= 2000:
                    return "invalid message text"
                if p.get("claim") is not None and (type(p["claim"]) not in (int, float) or not 0 <= p["claim"] <= 100):
                    return "invalid claim"
        if kind in {"send", "relay"}:
            if used["communication"] >= characters.limit(self,a,"communication",self.config.communication_budget):
                return "communication budget exhausted"
            if not self.edge(a.id, p.get("target")):
                return "no communication path"
            if kind == "send":
                if p.get("agenda_id") is not None:
                    reason=agenda.validate_send(self,a,p)
                    if reason:return reason
                elif p.get("topic", "").startswith("agenda:") if isinstance(p.get("topic",""),str) else False:
                    return "agenda topics require structured local issue"
                if p.get("gathering_id") is not None:
                    gid = p["gathering_id"]
                    if not collective.enabled(self) or not isinstance(gid,str) or gid not in collective.state(a)["known_gatherings"]:
                        return "gathering not learned"
                    if gid not in self.gatherings or self.time >= self.gatherings[gid]["end"]:
                        return "gathering ended"
                audience = p.get("audience")
                if audience is not None and (not isinstance(audience, list) or any(not isinstance(x, str) or x not in self.agents for x in audience) or p["target"] not in audience):
                    return "invalid or inaccessible audience"
                if not isinstance(p.get("topic", "general"), str) or not 0 < len(p.get("topic", "general")) <= 200:
                    return "invalid topic"
                if not isinstance(p.get("text"), str) or not 0 < len(p["text"]) <= 2000:
                    return "invalid message text"
                if p.get("claim") is not None and (type(p["claim"]) not in (int, float) or not 0 <= p["claim"] <= 100):
                    return "invalid claim"
            if kind == "relay" and isinstance(p.get("message_id"), str) and p.get("message_id") in self.messages:
                scope = self.messages[p["message_id"]].get("audience")
                if scope is not None and p["target"] not in scope:
                    return "outside message audience"
            if kind == "relay" and not any(m.get("message_id") == p.get("message_id") for m in a.memories):
                return "message not learned"
        if kind == "declare_support" and (type(p.get("value")) not in (int, float) or not 0 <= p["value"] <= 1):
            return "invalid support value"
        if kind in {"pressure", "revoke_contract"}:
            if kind not in a.permissions:
                return "permission denied"
            if not isinstance(p.get("target"), str) or p.get("target") not in self.agents or p["target"] == a.id:
                return "invalid target"
            target = self.agents[p["target"]]
            if target.authority_dependency != a.id:
                return "target outside authority scope"
            if characters.enabled(self) and self.authorities[a.id]["institutional_power"]<=0:
                return "institution has no remaining authority"
            if a.savings < 2:
                return "insufficient resources"
        return None

    def run(self, until: int, provider: DecisionProvider | None = None, max_events=100000):
        if type(until) is not int or until < self.time:
            raise ValueError("Cannot run backwards")
        provider = provider or BaselineProvider()
        count = 0
        while self.queue and self.queue[0][0] <= until:
            if count >= max_events:
                raise RuntimeError("Event limit reached; state remains resumable")
            time, order, eid, kind, payload, cause = heapq.heappop(self.queue)
            self.time = time
            if eid in self.processed:
                continue
            # Restore an event if provider/processing fails. Provider is called before
            # decision-side mutation; persisted responses are used on a retry.
            try:
                outcome = self._handle(eid, kind, payload, provider)
            except Exception:
                heapq.heappush(self.queue, (time, order, eid, kind, payload, cause))
                raise
            self.processed.add(eid)
            self.record(kind if outcome is not False else kind + "_skipped", payload, cause, event_id=eid)
            count += 1
        self.time = until

    def _handle(self, eid, kind, p, provider):
        if kind in agenda.EVENTS:
            agenda.handle(self,kind,p,eid,provider)
        elif kind == "daily":
            day = self.time // 1440
            if day <= self.last_daily_day:
                return False
            self.last_daily_day = day
            employer_health = {}
            if psychology.enabled(self):
                # Halk boykotu veya aktif protesto buluşmaları ticari/zengin işverenlerin cirosunu vurur
                open_attendees = set()
                if collective.enabled(self) and hasattr(self, "gatherings"):
                    for g in self.gatherings.values():
                        if g["start"] <= self.time < g["end"]:
                            open_attendees.update(g.get("participants", ()))
                boycott_signal = float(self.protocol.get("active_boycott", 0.0))
                crowd_ratio = len(open_attendees) / max(1, len(self.agents))
                boycott_level = min(0.35, max(boycott_signal, crowd_ratio * 1.6 if crowd_ratio >= 0.05 else 0.0))
                for w in self.agents.values():
                    if w.initial_group != "wealthy":
                        continue
                    ec = w.behavior.setdefault("economic_chain", {"contract_factor": 1.0, "boycott_penalty": 0.0, "employer_cut": 0.0})
                    sw = w.behavior.get("subwing")
                    if boycott_level > 0:
                        weight = 1.0 if sw in ("pro_A", "neutral_commercial") else 0.55
                        ec["boycott_penalty"] = min(0.35, boycott_level * weight)
                    else:
                        ec["boycott_penalty"] = 0.0 if ec["boycott_penalty"] < 0.03 else ec["boycott_penalty"] * 0.55
                    health = max(0.25, min(1.0, ec["contract_factor"] * (1.0 - ec["boycott_penalty"])))
                    employer_health[w.id] = health
                    # Yaptırım olmayan sakin günlerde sözleşme çarpanı kademeli toparlanır
                    if boycott_level == 0 and ec["contract_factor"] < 1.0:
                        ec["contract_factor"] = min(1.0, ec["contract_factor"] + 0.03)
                # Tek günlük boykot sinyali işlendikten sonra yumuşar
                if boycott_signal > 0:
                    self.protocol["active_boycott"] = 0.0 if boycott_signal < 0.06 else round(boycott_signal * 0.55, 4)

            for a in self.agents.values():
                self._refresh_budget(a)
                expense = a.expense * self.price
                eff_income = a.income
                emp_cut = 0.0
                if employer_health:
                    ec = a.behavior.setdefault("economic_chain", {"contract_factor": 1.0, "boycott_penalty": 0.0, "employer_cut": 0.0})
                    if a.initial_group == "wealthy" and a.id in employer_health:
                        h = employer_health[a.id]
                        if h < 0.9999:
                            emp_cut = round(1.0 - h, 4)
                            eff_income = a.income * h
                    elif a.employer in employer_health and employer_health[a.employer] < 0.98:
                        emp_cut = round(0.65 * (1.0 - employer_health[a.employer]), 4)
                        eff_income = a.income * (1.0 - emp_cut)
                    ec["employer_cut"] = emp_cut
                a.savings += eff_income - expense
                loss = max(0., expense - a.expense) + max(0., a.income - eff_income)
                a.losses += loss
                # Personal expense is observable; global prices/power are not injected.
                mem = {"event_id": eid, "type": "direct_experience",
                       "learned_at": self.time, "expense": expense, "income": eff_income}
                if emp_cut > 0:
                    mem["employer_cut"] = emp_cut
                a.memories.append(mem)
                self.schedule(self.time, "read", {"target": a.id}, eid)
                self.schedule(self.time, "behavior", {"target": a.id, "expense": expense}, eid)
            self.schedule(self.time + 1439, "day_end", {}, eid)
            self.schedule(self.time + 1440, "daily", {}, eid)
        elif kind == "price_shock":
            if type(p.get("multiplier")) not in (int, float) or not 0 < p["multiplier"] <= 10:
                raise ValueError("Invalid price multiplier")
            self.price *= p["multiplier"]
        elif kind == "local_disruption":
            a=self.agents[p["target"]]
            characters.disruption(self,a,p["domain"],p["severity"],eid)
            self.schedule(self.time,"decide",{"target":a.id},eid)
        elif kind == "power_change":
            if p.get("pole") not in self.pole_power or type(p.get("value")) not in (int, float) or not 0 <= p["value"] <= 100:
                raise ValueError("Invalid power change")
            self.pole_power[p["pole"]] = p["value"]
        elif kind == "delivery":
            a = self.agents[p["target"]]
            if self.edge(p["sender"], a.id) and p["message_id"] in self.messages:
                if not any(m.get("message_id") == p["message_id"] for m in a.memories) and p["message_id"] not in [x["message_id"] for x in a.inbox]:
                    a.inbox.append({**deepcopy(p), "delivered_at": self.time})
                    self.schedule(self.time, "read", {"target": a.id}, eid)
        elif kind == "read":
            a = self.agents[p["target"]]
            self._refresh_budget(a)
            while a.inbox and a.used["read"] < characters.limit(self,a,"read",self.config.read_budget):
                delivery = a.inbox.pop(0)
                m = self.messages[delivery["message_id"]]
                a.used["read"] += 1
                a.memories.append({"event_id": eid, "message_id": m["id"],
                    "learned_at": self.time, "delivered_at": delivery["delivered_at"], "sender": delivery["sender"],
                    "original_source": m["original_source"], "source_group": m["source_group"], "source_alignment": m["source_alignment"], "topic": m["topic"], "text": m["text"], "claim": m["claim"]})
                self._belief_update(a, m, delivery["sender"])
                self.schedule(self.time, "decide", {"target": a.id}, eid)
        elif kind == "external_action":
            # Admin-scheduled scenario input, never a capability given to providers.
            self.apply(self.propose(p["actor"], p["proposal"], eid))
        elif kind == "behavior":
            a = self.agents[p["target"]]
            if self.config.cumulative_enabled and self.behavior_profile["dynamics"]["enabled"]:
                dynamics.daily(self, a, p["expense"], eid)
                if collective.enabled(self):
                    local = collective.state(a)
                    withdrawal = (a.public_support > 0 and a.private_loyalty < .5 and
                        a.behavior.get("appraisal",{}).get("responsibility_current",0.) > 0)
                    ongoing = local["present_at"] is None and any(
                        g["start"] <= self.time < g["end"] for g in local["known_gatherings"].values())
                    if characters.enabled(self):
                        c=characters.state(a)
                        reference,reason=characters.policy(self.observation(a.id))
                        c["decision_reason"]=reason
                        self.record("daily_response_appraisal",{"agent":a.id,"reason":reason,
                            "reference_action":reference,"reason_scope":"reference_policy"},eid)
                        ongoing=ongoing or (reference is not None and reference["type"]!="wait")
                        withdrawal=withdrawal or (a.public_support>0 and a.private_loyalty<.5 and bool(c["verified_failures"]))
                        ongoing=ongoing or a.initial_group in ("observer","authority","discontented") or (a.public_support==0 and bool(c["verified_recoveries"]))
                    if withdrawal or ongoing:
                        self.schedule(self.time,"decide",{"target":a.id},eid)
        elif kind == "gathering_close":
            collective.close(self,p["gathering_id"],eid)
        elif kind == "day_end":
            self.daily_metrics.append({"time": self.time, **self.behavior_metrics()})
        elif kind == "decide":
            a = self.agents[p["target"]]
            self._refresh_budget(a)
            if a.used["action"] >= self.config.action_budget:
                self.record("decision_budget_blocked", {"agent": a.id}, eid)
                return
            cached = next((c for c in self.calls if c["event"] == eid), None)
            if cached is None:
                obs = self.observation(a.id)
                if characters.enabled(self):
                    _, reason=characters.policy(obs)
                    characters.state(a)["decision_reason"]=reason
                    self.record("decision_appraisal",{"agent":a.id,"reason":reason,"reason_scope":"reference_policy", "policy":type(provider).__name__},eid)
                response = self._safe_proposal(provider.decide(deepcopy(obs)))
                self.calls.append({"event": eid, "observation": obs, "response": deepcopy(response)})
            else:
                response = cached["response"]
            did = self.propose(a.id, response, eid)
            self.apply(did)
        else:
            raise ValueError(f"Unknown event type: {kind}")

    def _belief_update(self, a, m, sender):
        if agenda.enabled(self) and "agenda" in m:
            agenda.receive(self,a,m,sender)
            return
        if characters.enabled(self) and characters.receive(self,a,m,sender):
            collective.receive(self,a,m,sender)
            return
        dynamics.message(self, a, m, sender)
        if collective.enabled(self):
            collective.receive(self,a,m,sender)
        from . import appraisal
        if appraisal.enabled(self) and (m["topic"].startswith("responsibility:") or m["topic"].startswith("benefit:") or m["topic"].startswith("alternative_known:")):
            return
        # In this prototype the original source is authenticated by the engine.
        # No spoofing or unverified source attribution is modeled yet.
        settings = self.behavior_profile["groups"][a.initial_group]
        if settings["requires_aligned_authority"]:
            if m["source_group"] != "authority" or m["source_alignment"] != a.alignment:
                return
        if m["claim"] is None:
            return
        edge = self.edge(sender, a.id)
        previous = a.beliefs.get(m["topic"], {}).get("estimate", 50.)
        if abs(m["claim"] - previous) / 100 < a.traits["topic_change_threshold"]:
            return
        factor = 1.
        if self.config.cumulative_enabled and self.behavior_profile["dynamics"]["enabled"]:
            if m["source_group"] == "authority":
                factor = a.traits["authority_sensitivity"] * a.behavior["trust"].get(m["original_source"], edge["trust"])
            else:
                factor = 0. if self.config.ablation == "peer" else 1-a.traits["peer_opinion_resistance"]
        weight = edge["trust"] * self.behavior_profile["belief_step"] * factor
        old_estimate = previous
        a.beliefs[m["topic"]] = {"estimate": previous + weight * (m["claim"] - previous),
                                 "evidence": m["id"], "updated_at": self.time}
        self.record("belief_updated", {"agent": a.id, "topic": m["topic"], "old": old_estimate,
            "new": a.beliefs[m["topic"]]["estimate"], "message_id": m["id"]}, m["id"])

    def behavior_metrics(self):
        agents = list(self.agents.values())
        trusts = [v for a in agents for v in a.behavior.get("trust", {}).values()]
        return {"mean_private_loyalty": sum(a.private_loyalty for a in agents)/len(agents),
                "mean_support_gap": sum(abs(a.public_support-a.private_loyalty) for a in agents)/len(agents),
                "mean_trust": sum(trusts)/len(trusts) if trusts else None,
                "alignment_changes": sum(a.behavior.get("switch_count", 0) for a in agents),
                "core_changes": sum(a.behavior.get("core_changes", 0) for a in agents),
                "losses": sum(a.losses for a in agents)}

    def metrics(self):
        agents = list(self.agents.values())
        reach = {mid: [a.id for a in agents if any(m.get("message_id") == mid for m in a.memories)] for mid in self.messages}
        latency = {mid: [m["learned_at"] - self.messages[mid]["created_at"]
                        for a in agents for m in a.memories if m.get("message_id") == mid] for mid in self.messages}
        # Only agents with an explicit estimate participate; unknown is not zero error.
        errors = [abs(a.beliefs[f"power:{pole}"]["estimate"] - value)
                  for a in agents for pole, value in self.pole_power.items() if f"power:{pole}" in a.beliefs]
        return {"time": self.time, "population": len(agents), "reach": reach,
            "delivery_latency_minutes": latency,
            "mean_support_gap": sum(abs(a.public_support - a.private_loyalty) for a in agents) / len(agents),
            "alignment_changes": sum(e["kind"] == "alignment_changed" for e in self.log),
            "losses_by_group": {g: sum(a.losses for a in agents if a.initial_group == g) for g in GROUPS},
            "perception_error": sum(errors) / len(errors) if errors else None,
            "perception_sample_count": len(errors),
            "rejected_actions": sum(e["kind"] == "action_rejected" for e in self.log),
            "provider_calls": len(self.calls)}

    def save(self, path):
        data = {"version": VERSION, "behavior_profile": self.behavior_profile, "config": asdict(self.config), "time": self.time,
                "daily_metrics": self.daily_metrics, "experiment_id": self.experiment_id, "last_daily_day": self.last_daily_day, "seq": self.seq, "queue": self.queue, "processed": sorted(self.processed),
                "agents": {k: asdict(v) for k, v in self.agents.items()}, "edges": self.edges,
                "authorities": self.authorities, "messages": self.messages, "log": self.log,
                "decisions": self.decisions, "calls": self.calls, "price": self.price,
                "pole_power": self.pole_power, "protocol": self.protocol, "rng": self.rng.getstate()}
        if collective.enabled(self):
            data["gatherings"] = self.gatherings
        if agenda.enabled(self):
            data["agendas"]=self.agendas
            data["agenda_runtime"]=self.agenda_runtime
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        temp.replace(path)

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        version = data.pop("version")
        if version not in (1, VERSION):
            raise ValueError("Unsupported snapshot version")
        if version == 1:
            cls._migrate_v1(data)
        data["behavior_profile"] = validate_profile(data["behavior_profile"])
        obj = cls.__new__(cls)
        config_data = data.pop("config")
        if "cumulative_enabled" not in config_data:
            config_data["cumulative_enabled"] = False
        obj.config = Config(**config_data)
        data.setdefault("daily_metrics", [])
        data.setdefault("experiment_id", "legacy")
        def tuples(x):
            return tuple(tuples(y) for y in x) if isinstance(x, list) else x
        obj.rng = random.Random()
        obj.rng.setstate(tuples(data.pop("rng")))
        obj.agents = {k: Agent(**v) for k, v in data.pop("agents").items()}
        obj.processed = set(data.pop("processed"))
        obj.queue = [tuple(e) for e in data.pop("queue")]
        heapq.heapify(obj.queue)
        obj.__dict__.update(data)
        if collective.enabled(obj):
            obj.__dict__.setdefault("gatherings",{})
            for a in obj.agents.values():
                collective.state(a)
        obj._initialize_behavior()
        if agenda.enabled(obj):
            obj.__dict__.setdefault("agendas",{})
            obj.__dict__.setdefault("agenda_runtime",{"cache":{},"requests":[],"daily_counts":{},"network_requests":0})
        if characters.enabled(obj):
            for a in obj.agents.values():characters.state(a)
        if psychology.enabled(obj):
            for a in obj.agents.values():
                psychology.state(a)
        return obj

    @staticmethod
    def _migrate_v1(data):
        """Preserve historical draws/state; fill new fields without consuming RNG."""
        profile = load_profile()
        data["last_daily_day"] = max((e["time"] // 1440 for e in data["log"] if e["kind"] == "daily"), default=-1)
        data["behavior_profile"] = profile
        data["protocol"]["migration"] = "v1 -> v2; new traits use interval midpoints, no RNG draws"
        data["protocol"]["behavior_profile"] = deepcopy(profile)
        for a in data["agents"].values():
            settings = profile["groups"][a["initial_group"]]
            for field in ("traits", "initial_traits"):
                for name, bounds in settings["parameters"].items():
                    a[field].setdefault(name, a[field]["resistance"] if name == "core_orientation_resistance" else sum(bounds) / 2)
                for name, bounds in settings.get("psychology", {}).items():
                    a[field].setdefault(name, sum(bounds) / 2)
            a["budget_day"] = data["time"] // 1440
            for item in a["inbox"]:
                item.setdefault("delivered_at", data["time"])
        for m in data["messages"].values():
            source = data["agents"][m["original_source"]]
            m.setdefault("source_group", source["initial_group"])
            m.setdefault("source_alignment", source["alignment"])
        for event in data["queue"]:
            if event[3] == "daily":
                event[1] = -abs(event[1])

    def fork(self, path):
        self.save(path)
        return self.load(path)
