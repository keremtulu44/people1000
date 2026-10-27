"""Versioned experimental profiles. All ranges are closed normalized intervals."""
from copy import deepcopy
import json
import math
from pathlib import Path

from .dynamics import DEFAULT_DYNAMICS

PARAMETERS = {
    "authority_sensitivity", "peer_opinion_resistance", "economic_harm_response",
    "pressure_response", "topic_change_threshold", "alignment_change_threshold",
    "core_orientation_resistance",
}

PSYCHOLOGY_PARAMETERS = {
    "tolerance_threshold", "fear_sensitivity", "comfort_baseline",
    "defense_strength", "exhaustion_rate",
}

PSYCHOLOGY_DYNAMICS_KEYS = {
    "fear_retention", "anger_retention", "repressed_retention",
    "comfort_recovery", "defense_erosion", "defense_recovery",
    "exhaustion_step", "exhaustion_recovery", "peer_pull_retention",
}


def _valid_interval(bounds):
    return (isinstance(bounds, list) and len(bounds) == 2 and all(
        type(x) in (int, float) and math.isfinite(x) for x in bounds
    ) and 0 <= bounds[0] <= bounds[1] <= 1)


def validate_profile(profile):
    if profile.get("schema_version") != 1 or not isinstance(profile.get("behavior_version"), str):
        raise ValueError("Unsupported behavior profile version")
    if profile.get("decision_model", "legacy-v2") not in ("legacy-v2", "attributed-v1"):
        raise ValueError("Unknown decision model")
    if profile.get("social_model") not in (None, "collective-v1"):
        raise ValueError("Unknown social model")
    if profile.get("character_model") not in (None, "local-v1"):
        raise ValueError("Unknown character model")
    if profile.get("character_model"):
        if profile.get("social_model")!="collective-v1" or profile.get("decision_model")!="attributed-v1":
            raise ValueError("Local characters require collective and attributed models")
        cfg=profile.get("character_dynamics",{})
        keys={"adaptation_days","fatigue_days","study_step","observer_incoming_limit","observer_read_limit","observer_communication_limit","competition_cost","competition_transfer","institutional_ambition_scale","competition_cooldown_days","gathering_cooldown_days"}
        if set(cfg)!=keys or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in cfg.values()):
            raise ValueError("Invalid character assumptions")
        for key in keys:
            if (key.endswith("limit") or key.endswith("cooldown_days")) and type(cfg[key]) is not int:
                raise ValueError("Character limits/durations require integers")
        if any(cfg[k]<1 for k in ("adaptation_days","fatigue_days")) or any(cfg[k]>1 for k in ("study_step","competition_transfer")):
            raise ValueError("Invalid bounded learning/competition rates")
    if profile.get("agenda_model") not in (None,"local-agenda-v1"):
        raise ValueError("Unknown agenda model")
    if profile.get("agenda_model"):
        if profile.get("character_model")!="local-v1":raise ValueError("Agenda requires local characters")
        cfg=profile.get("agenda_dynamics",{})
        if set(cfg)!={"partisan_prior_strength","claim_step","daily_review_limit","total_review_limit"}:
            raise ValueError("Invalid agenda assumptions")
        for k,v in cfg.items():
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError("Invalid agenda coefficient")
            if k.endswith("limit") and type(v) is not int:raise ValueError("Review budgets require integers")
            if not k.endswith("limit") and v>1:raise ValueError("Agenda rates must be bounded")
    if profile.get("psychology_model") not in (None, "affective-v1", "affective-v2"):
        raise ValueError("Unknown psychology model")
    if profile.get("psychology_model"):
        if profile.get("character_model") != "local-v1":
            raise ValueError("Affective psychology requires local characters")
        pcfg = profile.get("psychology_dynamics", {})
        if set(pcfg) != PSYCHOLOGY_DYNAMICS_KEYS:
            raise ValueError("Invalid psychology dynamics keys")
        for v in pcfg.values():
            if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1:
                raise ValueError("Psychology dynamics rates must lie in [0, 1]")
    expected = {"power_aligned", "opposition", "authority", "wealthy", "discontented", "observer"}
    if set(profile.get("groups", {})) != expected:
        raise ValueError("Exactly six groups are required")
    for gname, group in profile["groups"].items():
        if type(group.get("population_percent")) is not int or group["population_percent"] <= 0:
            raise ValueError("Invalid population percentage")
        if type(group.get("requires_aligned_authority")) is not bool:
            raise ValueError("Invalid authority gate")
        if set(group.get("parameters", {})) != PARAMETERS:
            raise ValueError("Missing or unknown behavior parameter")
        for bounds in [*group["parameters"].values(), group.get("risk_tolerance")]:
            if not _valid_interval(bounds):
                raise ValueError("Parameter ranges must be finite ordered intervals in [0, 1]")
        if profile.get("psychology_model"):
            psych = group.get("psychology", {})
            if set(psych) != PSYCHOLOGY_PARAMETERS or any(not _valid_interval(b) for b in psych.values()):
                raise ValueError("Missing or invalid group psychology bounds")
            if gname == "wealthy" and "neutral_defense_strength" in group:
                if not _valid_interval(group["neutral_defense_strength"]):
                    raise ValueError("Invalid wealthy neutral defense bounds")
    if sum(g["population_percent"] for g in profile["groups"].values()) != 100:
        raise ValueError("Population percentages must sum to 100")
    step = profile.get("belief_step")
    if type(step) not in (int, float) or not math.isfinite(step) or not 0 <= step <= 1:
        raise ValueError("Invalid belief step")
    profile = deepcopy(profile)
    # Old profiles retain cumulative behavior only when explicitly upgraded.
    if "dynamics" not in profile:
        profile["dynamics"] = {**DEFAULT_DYNAMICS, "enabled": False}
    if set(profile["dynamics"]) != set(DEFAULT_DYNAMICS):
        raise ValueError("Missing or unknown dynamics coefficient")
    for key, value in profile["dynamics"].items():
        if key == "enabled":
            if type(value) is not bool:
                raise ValueError("enabled must be boolean")
        elif type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Dynamics coefficients must be finite and nonnegative")
        elif (key.endswith("retention") or key in {"trust_erosion", "trust_recovery", "loyalty_step", "core_step"}) and value > 1:
            raise ValueError("Rate must lie in [0,1]")
    return profile


def load_profile(path=None):
    return validate_profile(json.loads(Path(path or Path(__file__).with_name("behavior.json")).read_text(encoding="utf-8")))


def sample_traits(rng, group, subwing=None):
    traits = {name: rng.uniform(*bounds) for name, bounds in group["parameters"].items()}
    traits["risk_tolerance"] = rng.uniform(*group["risk_tolerance"])
    if "psychology" in group:
        for name, bounds in group["psychology"].items():
            if name == "defense_strength" and subwing == "neutral_commercial" and "neutral_defense_strength" in group:
                traits[name] = rng.uniform(*group["neutral_defense_strength"])
            else:
                traits[name] = rng.uniform(*bounds)
    # Backward-compatible name used by the original reference engine.
    traits["resistance"] = traits["core_orientation_resistance"]
    return traits


def load_legacy_profile():
    """Frozen v2 comparison; never silently replace a historical model."""
    return load_profile(Path(__file__).with_name("behavior-v2.json"))


def load_v3_profile():
    """Frozen pre-collective v3.0, including its documented limitations."""
    return load_profile(Path(__file__).with_name("behavior-v3.json"))


def load_v31_profile():
    """Frozen v3.1 before character-local reasoning and physical co-presence."""
    return load_profile(Path(__file__).with_name("behavior-v31.json"))


def load_v32_profile():
    """Frozen pre-agenda v3.2. No implicit upgrade."""
    return load_profile(Path(__file__).with_name("behavior-v32.json"))


def load_v33_profile():
    """Frozen pre-affective v3.3. Preserves historical 808-run research profile."""
    return load_profile(Path(__file__).with_name("behavior-v33.json"))


def load_v34_profile():
    """Frozen v3.4 (affective-v1) profile before v3.5 deep social-mind calibration."""
    return load_profile(Path(__file__).with_name("behavior-v34.json"))

