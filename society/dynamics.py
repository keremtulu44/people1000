"""Bounded sufficient statistics, updated only by local observations.

No access to global price/power or other agents' private state. All coefficients
are experimental assumptions; changes are logged with the causal observation.
"""
from statistics import mean
from copy import deepcopy

DEFAULT_DYNAMICS = {
    "enabled": True, "burden_retention": .90, "evidence_retention": .96,
    "trust_erosion": .12, "trust_recovery": .04, "forecast_days": 7,
    "evidence_economic": .08, "evidence_distrust": .12, "evidence_peer": .05,
    "loyalty_step": .08, "return_margin": .30, "cooldown_days": 5,
    "core_retention": 1.0, "core_step": .015, "core_threshold_scale": 12.,
    "core_min_days": 14, "pressure_retention": .85,
}


def clamp(x, lo=0., hi=1.):
    return max(lo, min(hi, x))


def initialize(a, known=None):
    if a.behavior:
        return
    a.behavior = {
        "burden": 0., "reference_income": a.income, "trust": {}, "forecasts": {},
        "known": known or {}, "peer_pull": {"A": 0., "B": 0.},
        "last_switch_day": -1000, "previous_alignment": None, "switch_count": 0,
        "core_strain": 0., "core_orientation": 1., "core_changes": 0,
        "observed_days": 0, "harm": 0., "dependency_loss": 0.,
    }
    for source, info in a.behavior["known"].items():
        if info["group"] == "authority":
            a.behavior["trust"][source] = info["trust"]


def message(sim, a, m, sender):
    if not sim.config.cumulative_enabled or not sim.behavior_profile["dynamics"]["enabled"]:
        return
    initialize(a)
    s = a.behavior
    edge = sim.edge(sender, a.id)
    source = m["original_source"]
    s["known"][source] = {"pole": m["source_alignment"], "group": m["source_group"],
                          "trust": edge["trust"]}
    from . import psychology
    is_partisan_broadcast = (
        psychology.v2_enabled(sim)
        and m["source_group"] == "wealthy"
        and m["source_alignment"] in ("A", "B")
    )
    if m["source_group"] == "authority" or is_partisan_broadcast:
        s["trust"].setdefault(source, edge["trust"])
        if m["topic"] == "economic_outlook" and m["claim"] is not None:
            s["forecasts"][source] = {"prediction": m["claim"] / 100,
                "learned_at": sim.time, "message_id": m["id"], "source_pole": m["source_alignment"]}
    elif m["topic"] == "public_support" and m["claim"] is not None:
        pole = m["source_alignment"]
        if pole in ("A", "B"):
            # Perceived public behavior, not access to the source's private loyalty.
            resistance = 1. if sim.config.ablation == "peer" else a.traits["peer_opinion_resistance"]
            s["peer_pull"][pole] = clamp(s["peer_pull"][pole] +
                (1-resistance) * edge["trust"] * m["claim"] / 100)
    from . import appraisal
    if appraisal.enabled(sim):
        appraisal.receive(sim, a, m, sender)
    sim.record("social_observation", {"agent": a.id, "message_id": m["id"],
        "sender": sender, "original_source": source, "learned_at": sim.time}, m["id"])


def daily(sim, a, expense, cause):
    if not sim.config.cumulative_enabled or not sim.behavior_profile["dynamics"]["enabled"]:
        return
    initialize(a)
    s, t = a.behavior, a.traits
    cfg = sim.behavior_profile["dynamics"]
    day = sim.time // 1440
    prior_views = deepcopy(a.beliefs)
    trust_changes = []
    exposure = s.setdefault("diagnostic_exposure", {"tracking_start": sim.time,
        "observed_days": 0, "harm_days": 0, "first_harm_at": None, "excess_cost": 0.})
    exposure["observed_days"] += 1
    s["observed_days"] += 1
    emp_cut = a.behavior.get("economic_chain", {}).get("employer_cut", 0.0) if isinstance(a.behavior.get("economic_chain"), dict) else 0.0
    income_harm = clamp(max(0., s["reference_income"] - a.income) / max(1., s["reference_income"]) + emp_cut)
    harm = clamp(max(0., expense - a.expense) / max(1., a.expense) + income_harm)
    if harm > 0:
        exposure["harm_days"] += 1
        if exposure["first_harm_at"] is None:
            exposure["first_harm_at"] = sim.time
    exposure["excess_cost"] += max(0., expense-a.expense)
    s["harm"] = harm
    s["dependency_loss"] = income_harm
    s["burden"] = s["burden"] * cfg["burden_retention"] + harm * t["economic_harm_response"]
    # Directly observed cost harm is a private topic, not political affiliation.
    if harm > 0 or "experienced_harm" in a.beliefs:
        old = a.beliefs.get("experienced_harm", {}).get("estimate", 0.)
        if abs(harm - old/100) >= t["topic_change_threshold"]:
            a.beliefs["experienced_harm"] = {"estimate": 100*harm,
                                             "evidence": cause, "updated_at": sim.time}
            if old != 100*harm:
                sim.record("belief_updated", {"agent": a.id, "topic": "experienced_harm",
                    "old": old, "new": 100*harm, "evidence": cause}, cause)
    from . import psychology
    if psychology.enabled(sim):
        pcfg = sim.behavior_profile["psychology_dynamics"]
        for pole in ("A", "B"):
            s["peer_pull"][pole] *= pcfg["peer_pull_retention"]
    # The authority forecast is compared only with later personal expenses/income.
    max_own_error = 0.
    for source, f in list(s["forecasts"].items()):
        age = sim.time - f["learned_at"]
        if age <= 0:
            continue
        if age > cfg["forecast_days"] * 1440:
            del s["forecasts"][source]
            continue
        error = abs(f["prediction"] - harm)
        own_source = s["known"].get(source, {}).get("pole") == a.alignment
        if own_source:
            max_own_error = max(max_own_error, error)
        old = s["trust"][source]
        erosion_scale = psychology.trust_erosion_multiplier(sim, a) if own_source else 1.
        delta = (-cfg["trust_erosion"] * erosion_scale * error * t["authority_sensitivity"] if error > .1
                 else cfg["trust_recovery"] * (1-error))
        if sim.config.ablation == "trust_erosion" and delta < 0:
            delta = 0.
        s["trust"][source] = clamp(old + delta)
        trust_changes.append({"source": source, "old": old, "new": s["trust"][source],
                              "message_id": f["message_id"]})
        sim.record("trust_updated", {"agent": a.id, "source": source, "old": old,
            "new": s["trust"][source], "error": error, "evidence": f["message_id"],
            "learned_at": f["learned_at"], "observed_harm": harm}, cause)
    from . import appraisal
    causal = appraisal.enabled(sim)
    evaluation = appraisal.assess(sim,a,cause,max(0.,expense-a.expense)/max(1.,a.expense),income_harm) if causal else None
    if causal:
        appraisal.update_burdens(a,evaluation,harm,t["economic_harm_response"],cfg["burden_retention"])
    responsibility = evaluation["shares_by_pole"].get(a.alignment,0.) if causal else 1.
    from . import collective, characters
    reaction=characters.temporal(sim,a,expense,income_harm,cause) if characters.enabled(sim) else harm
    if characters.enabled(sim):characters.track_trust(a,trust_changes)
    psych = None
    if psychology.enabled(sim):
        nonprice = max((d.get("level", 0.) for k, d in characters.state(a)["domains"].items()
                        if k not in ("living_cost", "income_security")), default=0.) if characters.enabled(sim) else 0.
        coll_active = bool(collective.state(a).get("collective_active")) if collective.enabled(sim) else False
        eff_own_error = max_own_error
        if a.initial_group == "observer" and characters.enabled(sim):
            verified_err = max((sa.get("error", 0.) for sa in characters.state(a).get("source_assessments", {}).values()), default=0.)
            eff_own_error = max(eff_own_error, verified_err)
        psych = psychology.daily(sim, a, harm, income_harm, nonprice, responsibility, eff_own_error, coll_active, cause)
    if collective.enabled(sim):
        collective.state(a)["distress"] = (psych["effective_drive"] if psych is not None
            else (reaction if characters.enabled(sim) else clamp(s["burden"])))
        appraisal.state(a)["responsibility_current"] = responsibility
    political_burden = appraisal.state(a)["burden_by_pole"].get(a.alignment,0.) if causal else s["burden"]
    own = [v for source, v in s["trust"].items()
           if s["known"].get(source, {}).get("pole") == a.alignment]
    distrust = 1-mean(own) if own else 0.
    known_poles = {v["pole"] for v in s["known"].values()}
    alt = "B" if a.alignment == "A" else "A"
    attraction = (.35 if alt in known_poles else 0.) + (0. if sim.config.ablation == "peer" else s["peer_pull"].get(alt,0.))
    if causal:
        attraction = evaluation["attraction"]
        if characters.enabled(sim):alt=evaluation["alternative"]
    # Separate group mechanisms, in addition to individually sampled coefficients.
    group = a.initial_group
    exit_cost = .15 + (1-t["risk_tolerance"]) * .2 + .1*s["core_orientation"]
    if group == "power_aligned":
        exit_cost += .15 * t["authority_sensitivity"]  # attachment to order
    elif group == "opposition":
        attraction += .10 * distrust * (attraction if causal else 1.)  # own authority disappointment, not global ruling-party knowledge
    elif group == "authority":
        # Known institutional allies vs alternative, never hidden live coalition data.
        allies = sum(v["pole"] == a.alignment for v in s["known"].values())
        exit_cost += .25 + min(.15, allies * .01)
        attraction += .25 * income_harm * (attraction if causal else 1.)
    elif group == "wealthy":
        exit_cost += .25 if a.authority_dependency else 0.
        attraction += .35 * income_harm * (attraction if causal else 1.)
    elif group == "discontented":
        attraction *= .5  # grievance is not durable allegiance
        exit_cost += .2
    elif group == "observer":
        exit_cost += .5
        attraction *= .3
    if psych is not None:
        exit_cost += .12 * psych["comfort"]
    peer_effect = (1-t["peer_opinion_resistance"]) * s["peer_pull"].get(alt,0.)
    if sim.config.ablation == "peer":
        # Keep receipt, authority forecasts, and source recognition unchanged.
        peer_effect = 0.
    evidence_before = a.change_evidence
    backlash = (0.03 * psych["repressed_anger"]
                if psych is not None and a.public_support - a.private_loyalty > 0.25
                and psych["repressed_anger"] > 0.30 and psych["fear"] < 0.30 else 0.)
    contributions = {"retained": evidence_before * cfg["evidence_retention"],
        "economic": 0. if sim.config.ablation == "economic_evidence" else cfg["evidence_economic"] * political_burden,
        "distrust": cfg["evidence_distrust"] * distrust * t["authority_sensitivity"] + backlash,
        "peer": cfg["evidence_peer"] * peer_effect, "relief": -.015*(1-harm)}
    # Attribution ledger is diagnostic only; it never enters the decision score.
    components = s.setdefault("diagnostic_evidence_components", {"economic": 0., "distrust": 0., "peer": 0., "relief": 0., "unattributed": evidence_before})
    residual = evidence_before-sum(components.values())
    components["unattributed"] += residual
    for name in components:
        components[name] *= cfg["evidence_retention"]
        if name in contributions:
            components[name] += contributions[name]
    a.change_evidence = max(0., sum(contributions.values()))
    if sum(contributions.values()) < 0:
        for name in components:
            components[name] = 0.
    old_loyalty = a.private_loyalty
    prior_adjustment=(.5-distrust)*.1
    if characters.enabled(sim) and not own:prior_adjustment=0.
    if characters.enabled(sim) and a.initial_group in ("authority","observer"):
        prior_adjustment=0.  # No generic verbal/initial-network popularity drift.
    loyalty_loss_scale = 1.
    if psych is not None:
        if psych["defense_wall"] >= 0.45:
            loyalty_loss_scale = 1.0 - 0.40 * psych["defense_wall"]
        elif psych["defense_wall"] < 0.35:
            loyalty_loss_scale = 1.0 + 0.35 * psych["repressed_anger"]
    a.private_loyalty = clamp(a.private_loyalty + cfg["loyalty_step"] *
        (prior_adjustment - reaction * t["economic_harm_response"] * responsibility * loyalty_loss_scale))
    threshold = t["alignment_change_threshold"] + exit_cost
    if alt == s["previous_alignment"]:
        threshold += cfg["return_margin"]  # return requires greater evidence
    eligible = (attraction >= .3 and a.change_evidence * attraction > threshold and
                day - s["last_switch_day"] >= cfg["cooldown_days"])
    # No categorical role lock: quarantined rhetoric supplies no attraction.
    # A valid locally evidenced alternative still uses the ordinary threshold.
    if eligible:
        diagnostic = {"schema_version": 1, "code_path": "society.dynamics.daily:eligible",
            "cause_event_id": cause, "initial_group": a.initial_group,
            "before": {"alignment": a.alignment, "private_loyalty": old_loyalty,
                "private_loyalty_after_daily_before_switch": a.private_loyalty,
                "public_alignment": a.public_alignment, "public_support": a.public_support,
                "core_orientation": s["core_orientation"], "views_before_daily": prior_views,
                "views_at_decision": deepcopy(a.beliefs), "pressure": a.pressure},
            "economic": {**exposure, "current_harm": harm, "burden": s["burden"],
                "recorded_losses": a.losses, "savings": a.savings, "income": a.income},
            "trust": deepcopy(s["trust"]), "trust_changes_today": trust_changes,
            "messages_learned": [{k:v for k,v in m.items() if k != "text"}
                                 for m in a.memories if "message_id" in m],
            "known_public_sources": deepcopy(s["known"]), "peer_pull": dict(s["peer_pull"]),
            "evidence_before": evidence_before, "evidence_terms_today": contributions,
            "accumulated_components": dict(components),
            "decision_score": a.change_evidence*attraction,
            "base_threshold": t["alignment_change_threshold"], "exit_cost": exit_cost,
            "returning": alt == s["previous_alignment"], "return_margin": cfg["return_margin"] if alt == s["previous_alignment"] else 0.,
            "last_switch_day": s["last_switch_day"], "elapsed_days": day-s["last_switch_day"],
            "cooldown_days": cfg["cooldown_days"], "attraction": attraction,
            "ablation": sim.config.ablation,
            **({"appraisal": deepcopy(evaluation), "attributed_burdens": deepcopy(appraisal.state(a))} if causal else {})}
        old = a.alignment
        accumulated_evidence = a.change_evidence
        a.alignment = alt
        s["previous_alignment"] = old
        s["last_switch_day"] = day
        s["switch_count"] += 1
        a.change_evidence = 0.
        for name in components:
            components[name] = 0.
        a.private_loyalty = .55
        sim.record("alignment_changed", {"agent": a.id, "old": old, "new": alt,
            "threshold": threshold, "attraction": attraction, "exit_cost": exit_cost,
            "burden": s["burden"], "distrust": distrust, "accumulated_evidence": accumulated_evidence, "diagnostic": diagnostic}, cause)
    # Deeper orientation is independent of party identity. Substantially slower.
    if not collective.enabled(sim):
        s["core_strain"] = s["core_strain"] * cfg["core_retention"] + harm * t["economic_harm_response"]
        core_threshold = cfg["core_threshold_scale"] / max(.001, 1-t["core_orientation_resistance"])
        if s["core_orientation"] > 0 and s["observed_days"] >= cfg["core_min_days"] and s["core_strain"] > core_threshold:
            old_core = s["core_orientation"]
            s["core_orientation"] = max(0., old_core - cfg["core_step"])
            s["core_strain"] = 0.
            s["core_changes"] += 1
            sim.record("core_orientation_changed", {"agent": a.id, "old": old_core,
                "new": s["core_orientation"], "threshold": core_threshold}, cause)
    a.pressure *= cfg["pressure_retention"]
    sim.record("behavior_updated", {"agent": a.id, "burden": s["burden"],
        "change_evidence": a.change_evidence, "loyalty_before": old_loyalty,
        "private_loyalty": a.private_loyalty, "harm": harm,
        "attraction": attraction, "threshold": threshold,
        **({"appraisal": evaluation, "political_burden": political_burden} if causal else {})}, cause)
