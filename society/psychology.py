"""v3.4/v3.5 affective & deep social-mind psychology layer.

Models tolerance thresholds, hedonic adaptation, fear & self-censorship,
asymptotic anger & repressed anger, intermediary-vs-leader blame shifting,
pluralistic ignorance & common-knowledge focal breaks, silent disengagement
('küskün seçmen'), relative deprivation, resource-bounded solidarity fatigue,
affective contagion, and observer epistemic whistleblowing.

Emotions are not cosmetic scores and NEVER trigger mass death/attack/suicide events.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import math

from .dynamics import clamp

WEALTHY_SUBWINGS = ("pro_A", "pro_B", "neutral_commercial")

SUBWING_LABELS_TR = {
    "pro_A": "A Kutbu Yanlısı Medya/Sermaye",
    "pro_B": "B Kutbu Yanlısı Medya/Sermaye",
    "neutral_commercial": "Tarafsız / Ticari Medya ve Sermaye",
}

DOMINANT_LABELS_TR = {
    "konfor_koruma": "Konfor ve Düzen Koruma",
    "rasyonalizasyon_savunmasi": "Psikolojik Savunma (Bahane / Rasyonalizasyon)",
    "suc_kaydirma": "Suç Kaydırma (Lider İyi, Aracılar Bozuk)",
    "kuskun_kopus": "Sessiz Kopuş / Küskün Seçmen (Gri Bölge)",
    "cogulcu_cehalet": "Çoğulcu Cehalet (Herkes Memnun Sanıp Yalnızlaşma)",
    "sabir_esiginde": "Tahammül Eşiği Altında (Sabrediyor)",
    "ofke_ve_itiraz": "Eşik Aşıldı — Açık Öfke ve İtiraz",
    "korku_otosansur": "Korku Baskın — Otosansür / Sessizlik",
    "bastirilmis_ofke": "İçeride Biriken Bastırılmış Tepki",
    "tukenmislik": "Tükenmişlik / Öğrenilmiş Çaresizlik",
    "sogukkanli_gozlem": "Mesafeli ve Uyanık Gözlem",
    "epistemik_uyari": "Epistemik Alarm — Teknik Uyarı Eşiğinde",
}

EXPRESSION_LABELS_TR = {
    "open": "Açık ifade",
    "guarded": "İmalı / ihtiyatlı dil",
    "self_censored": "Tam otosansür / sessizlik",
    "exhausted_withdrawal": "Yorgun kabulleniş / içe çekilme",
    "disengaged_silence": "Küskün sessizlik / sandıktan-söylemden çekilme",
    "epistemic_warning": "Kanıta dayalı teknik uyarı",
}


def enabled(sim):
    return sim.behavior_profile.get("psychology_model") in ("affective-v1", "affective-v2")


def v2_enabled(sim):
    return sim.behavior_profile.get("psychology_model") == "affective-v2"


def wealthy_subwing(index_in_group: int) -> str:
    return WEALTHY_SUBWINGS[index_in_group % len(WEALTHY_SUBWINGS)]


def pole_for_wealthy_subwing(subwing: str) -> str:
    if subwing == "pro_A":
        return "A"
    if subwing == "pro_B":
        return "B"
    return "none"


def _default_trait(a, key, fallback):
    return float(a.traits.get(key, fallback))


def _ensure_v2_fields(p, group: str):
    inter_default = 0.78 if group in ("power_aligned", "authority") else 0.52
    p.setdefault("adaptation_baseline", 0.0)
    p.setdefault("intermediary_trust", inter_default)
    p.setdefault("blame_shifted", False)
    p.setdefault("role_dissonance", 0.0)
    p.setdefault("disengaged", False)
    p.setdefault("pluralistic_ignorance", 0.0)
    p.setdefault("relative_deprivation", 0.0)
    p.setdefault("solidarity_capacity", 1.0)
    p.setdefault("epistemic_alarm", 0.0)
    p.setdefault("whistleblower_ready", False)
    return p


def state(a):
    subwing = a.behavior.get("subwing")
    comfort0 = _default_trait(a, "comfort_baseline", 0.5)
    defense0 = _default_trait(a, "defense_strength", 0.5)
    tol0 = _default_trait(a, "tolerance_threshold", 0.5)
    default_dom = "sogukkanli_gozlem" if a.initial_group == "observer" else (
        "konfor_koruma" if comfort0 >= 0.55 else "sabir_esiginde")
    p = a.behavior.setdefault("psychology", {
        "tolerance_threshold": tol0,
        "comfort": comfort0,
        "fear": 0.0,
        "anger": 0.0,
        "repressed_anger": 0.0,
        "exhaustion": 0.0,
        "defense_wall": defense0,
        "chronic_days": 0,
        "stressor": 0.0,
        "effective_drive": 0.0,
        "expression_mode": "open",
        "dominant_state": default_dom,
        "subwing": subwing,
        "conscience_insider": False,
    })
    return _ensure_v2_fields(p, a.initial_group)


def initialize(sim):
    if not enabled(sim):
        return
    for a in sim.agents.values():
        p = state(a)
        if a.initial_group == "authority":
            h = int(hashlib.sha256(f"{sim.config.seed}:{a.id}:insider".encode()).hexdigest()[:8], 16) / (16**8 - 1)
            # Small ~10% internal bureaucratic exception (~1-2 managers in 100 population).
            p["conscience_insider"] = h < 0.12
            if p["conscience_insider"]:
                p["defense_wall"] = clamp(p["defense_wall"] * 0.45)


def _local_social_context(sim, a) -> dict:
    """Strictly local neighborhood observations (no global God's-eye access)."""
    neighbors = []
    for e in sim.edges:
        if e["source"] == a.id:
            nb = sim.agents.get(e["target"])
            if nb is not None:
                neighbors.append(nb)
        elif e["target"] == a.id and e["type"] in ("close", "monitor", "media", "authority"):
            nb = sim.agents.get(e["source"])
            if nb is not None:
                neighbors.append(nb)
    if not neighbors:
        return {
            "silent_ratio": 0.0, "neighbor_fear": 0.0, "neighbor_anger": 0.0,
            "solidarity_capacity": 1.0, "elite_comfort": 0.0, "contradiction_spread": 0.0,
        }
    silent = 0
    fears, angers, sav_ratios, elite_comforts = [], [], [], []
    pole_claims = set()
    for nb in neighbors:
        np = nb.behavior.get("psychology") or {}
        n_expr = np.get("expression_mode", "open")
        if n_expr in ("self_censored", "guarded") or nb.public_support >= 0.62:
            silent += 1
        fears.append(float(np.get("fear", 0.0)))
        # Only open/visible anger is socially contagious; self-censored anger is hidden!
        vis_anger = float(np.get("anger", 0.0)) if n_expr == "open" else 0.0
        angers.append(vis_anger)
        ref_inc = max(1.0, float(nb.behavior.get("reference_income", nb.income or 10.0)))
        loss_strain = clamp(nb.losses / (ref_inc * 6.0))
        sav_ratios.append(1.0 - 0.75 * loss_strain)
        if nb.initial_group == "authority" or (nb.initial_group == "wealthy" and nb.behavior.get("subwing") == "pro_A"):
            elite_comforts.append(float(np.get("comfort", 0.72)))
        if nb.alignment in ("A", "B"):
            pole_claims.add(nb.alignment)
    n = len(neighbors)
    return {
        "silent_ratio": silent / n,
        "neighbor_fear": sum(fears) / n,
        "neighbor_anger": sum(angers) / n,
        "solidarity_capacity": clamp(sum(sav_ratios) / n, 0.18, 1.0),
        "elite_comfort": max(elite_comforts) if elite_comforts else 0.0,
        "contradiction_spread": 0.25 if len(pole_claims) >= 2 else 0.0,
    }


def _classify_expression_and_dominant(group, subwing, tol, stressor, comfort, fear,
                                      anger, repressed, exhaustion, defense_wall,
                                      use_v2=False, p=None):
    censorship_gate = 0.42 if subwing == "neutral_commercial" else 0.56
    guarded_gate = 0.22 if subwing == "neutral_commercial" else 0.30

    disengaged = bool(use_v2 and p and p.get("disengaged"))
    blame_shifted = bool(use_v2 and p and p.get("blame_shifted"))
    pi = float(p.get("pluralistic_ignorance", 0.0)) if (use_v2 and p) else 0.0
    wb = bool(use_v2 and p and p.get("whistleblower_ready"))

    if group == "observer" and wb and fear < 0.72:
        expr = "epistemic_warning"
    elif exhaustion >= 0.55 and exhaustion >= anger * 0.85:
        expr = "exhausted_withdrawal"
    elif fear >= censorship_gate:
        expr = "self_censored"
    elif disengaged and fear < censorship_gate and anger < 0.68:
        expr = "disengaged_silence"
    elif fear >= guarded_gate or pi >= 0.48:
        expr = "guarded"
    else:
        expr = "open"

    if group == "observer":
        dom = "epistemik_uyari" if wb else "sogukkanli_gozlem"
    elif expr == "exhausted_withdrawal":
        dom = "tukenmislik"
    elif disengaged and group in ("power_aligned", "opposition"):
        dom = "kuskun_kopus"
    elif expr == "self_censored" and repressed >= 0.28:
        dom = "bastirilmis_ofke"
    elif expr == "self_censored" or (fear >= guarded_gate and subwing == "neutral_commercial"):
        dom = "korku_otosansur"
    elif use_v2 and pi >= 0.48 and anger >= 0.28:
        dom = "cogulcu_cehalet"
    elif repressed >= 0.38 and repressed >= anger:
        dom = "bastirilmis_ofke"
    elif anger >= 0.35 and stressor >= tol:
        dom = "ofke_ve_itiraz"
    elif use_v2 and blame_shifted and stressor > 0.12 and group == "power_aligned":
        dom = "suc_kaydirma"
    elif stressor > 0.12 and defense_wall >= 0.55 and group in ("power_aligned", "authority"):
        dom = "rasyonalizasyon_savunmasi"
    elif stressor > 0.08 and stressor < tol:
        dom = "sabir_esiginde"
    else:
        dom = "konfor_koruma"
    return expr, dom


def _step_agent_psychology(p, traits, group, alignment, public_support, private_loyalty,
                           pressure, cfg, harm, income_harm, disruption_level,
                           responsibility_own, max_own_error, collective_supported,
                           threat_signal=0.0, coverup_signal=0.0, leak_signal=False,
                           use_v2=False, social_ctx=None):
    _ensure_v2_fields(p, group)
    tol = p["tolerance_threshold"]
    fear_sens = traits.get("fear_sensitivity", 0.4)
    comfort_base = traits.get("comfort_baseline", 0.5)
    defense_base = traits.get("defense_strength", 0.5)
    exh_rate = traits.get("exhaustion_rate", 0.4)
    harm_resp = traits.get("economic_harm_response", 0.5)
    peer_res = traits.get("peer_opinion_resistance", 0.5)
    subwing = p.get("subwing")
    sctx = social_ctx or {}

    # 1. Comfort / order satisfaction
    material_hit = clamp(0.75 * harm + 0.85 * income_harm + 0.65 * disruption_level + 0.30 * threat_signal)
    target_comfort = clamp(comfort_base * (1.0 - 0.85 * material_hit))
    if material_hit > 0.05:
        p["comfort"] = clamp(p["comfort"] - 0.35 * max(0.0, p["comfort"] - target_comfort))
    else:
        p["comfort"] = clamp(p["comfort"] + cfg["comfort_recovery"] * (comfort_base - p["comfort"]))

    # 2. v3.5 Blame Shifting (Intermediary vs Core Leader) + Role Dissonance + Defense Wall
    if use_v2:
        # Cross-cutting cleavage: e.g. power_aligned citizen hit by employer cut or severe income loss
        if alignment in ("A", "B") and (income_harm > 0.04 or max_own_error > 0.18):
            p["role_dissonance"] = clamp(0.84 * p["role_dissonance"] + 0.52 * income_harm + 0.30 * max_own_error)
        else:
            p["role_dissonance"] = clamp(0.86 * p["role_dissonance"])

        # Intermediaries ('bürokrasi / fırsatçılar') absorb the first wave of blame
        if material_hit > 0.08 or coverup_signal > 0.20:
            inter_drop = 0.14 * material_hit + 0.10 * coverup_signal + (0.18 if leak_signal else 0.0)
            p["intermediary_trust"] = clamp(p["intermediary_trust"] - inter_drop)
        else:
            inter_base = 0.78 if group in ("power_aligned", "authority") else 0.52
            p["intermediary_trust"] = clamp(p["intermediary_trust"] + 0.03 * (inter_base - p["intermediary_trust"]))

        # Blame stays on intermediaries ONLY while intermediary_trust >= 0.34, comfort >= 0.26, and no blatant lie/leak
        p["blame_shifted"] = bool(
            group == "power_aligned"
            and p["intermediary_trust"] >= 0.34
            and p["comfort"] >= 0.26
            and max_own_error < 0.28
            and not leak_signal
        )
        chronic_comfort_collapse = max(0.0, 0.34 - p["comfort"]) if not p["blame_shifted"] else 0.0
        if alignment in ("A", "B") and (harm > 0.02 or max_own_error > 0.1 or leak_signal or chronic_comfort_collapse > 0):
            leak_hit = 0.22 if leak_signal else 0.0
            shield = 0.35 if p["blame_shifted"] else 1.0
            erosion = cfg["defense_erosion"] * shield * (
                0.65 * harm * max(responsibility_own, 0.45 if chronic_comfort_collapse > 0 else 0.0)
                + 0.80 * max_own_error
                + 0.55 * chronic_comfort_collapse
                + 0.30 * p["role_dissonance"]
                + leak_hit
            ) * (1.15 - 0.45 * defense_base)
            p["defense_wall"] = clamp(p["defense_wall"] - erosion)
        elif p["comfort"] >= 0.40:
            p["defense_wall"] = clamp(p["defense_wall"] + cfg["defense_recovery"] * (defense_base - p["defense_wall"]))
    else:
        if alignment in ("A", "B") and (harm > 0.02 or max_own_error > 0.1 or leak_signal):
            leak_hit = 0.22 if leak_signal else 0.0
            erosion = cfg["defense_erosion"] * (
                0.65 * harm * responsibility_own + 0.80 * max_own_error + leak_hit
            ) * (1.15 - 0.45 * defense_base)
            p["defense_wall"] = clamp(p["defense_wall"] - erosion)
        else:
            p["defense_wall"] = clamp(p["defense_wall"] + cfg["defense_recovery"] * (defense_base - p["defense_wall"]))

    # 3. Fear + Subtle Affective Contagion
    contagion_fear = (0.08 * (1.0 - peer_res) * float(sctx.get("neighbor_fear", 0.0))
                      if use_v2 and group != "observer" else 0.0)
    fear_push = fear_sens * clamp(threat_signal + 0.45 * pressure + 0.35 * income_harm) + contagion_fear
    p["fear"] = clamp(max(p["fear"] * cfg["fear_retention"], fear_push) if threat_signal > 0
                      else p["fear"] * cfg["fear_retention"] + 0.35 * fear_push)

    # 4. Relative Deprivation (Görünür İmtiyaz Uçurumu) + Stressor vs Tolerance -> Asymptotic Anger
    if use_v2 and group in ("discontented", "opposition", "power_aligned") and (harm > 0.08 or income_harm > 0.06):
        elite_c = float(sctx.get("elite_comfort", 0.0))
        if elite_c <= 0.0 and coverup_signal > 0.35:
            elite_c = 0.72  # Visible protected privilege during cover-ups
        priv_gap = max(0.0, elite_c - p["comfort"] - 0.18)
        p["relative_deprivation"] = clamp(0.82 * p["relative_deprivation"] + 0.48 * priv_gap)
    else:
        p["relative_deprivation"] = clamp(0.85 * p["relative_deprivation"])

    injustice_push = coverup_signal * (
        0.75 if group in ("opposition", "discontented")
        else 0.55 if (group == "authority" and p.get("conscience_insider"))
        else 0.45 if subwing == "pro_B"
        else 0.12
    ) + (0.38 * p["relative_deprivation"] if use_v2 else 0.0)

    raw_stressor = clamp(
        harm * harm_resp * 1.30
        + 0.85 * disruption_level
        + 0.70 * income_harm
        + injustice_push
    )
    if group == "power_aligned" and p["defense_wall"] >= 0.45 and responsibility_own < 0.6:
        raw_stressor *= (1.0 - 0.45 * p["defense_wall"])
    p["stressor"] = clamp(raw_stressor)

    if use_v2:
        # Hedonic adaptation + asymptotic Weber-Fechner (`tanh`) anger prevents flat 1.000 saturation
        novel_shock = max(0.0, raw_stressor - p["adaptation_baseline"])
        p["adaptation_baseline"] = clamp(0.90 * p["adaptation_baseline"] + 0.10 * raw_stressor * 0.70)
        contagion_anger = (0.06 * (1.0 - peer_res) * float(sctx.get("neighbor_anger", 0.0))
                           if group != "observer" else 0.0)
        if raw_stressor <= tol:
            retained = p["anger"] * cfg["anger_retention"]
            p["anger"] = clamp(retained + (0.95 - retained) * 0.12 * raw_stressor + 0.5 * contagion_anger)
            p["chronic_days"] = max(0, p["chronic_days"] - 1)
        else:
            excess = (raw_stressor - tol) / max(0.18, 1.0 - tol)
            impulse = math.tanh(0.82 * excess + 0.85 * novel_shock + (0.35 if leak_signal else 0.0))
            retained = p["anger"] * cfg["anger_retention"]
            p["anger"] = clamp(retained + (0.96 - retained) * 0.58 * impulse + contagion_anger)
            p["chronic_days"] += 1
    else:
        if raw_stressor <= tol:
            p["anger"] = clamp(p["anger"] * cfg["anger_retention"] + 0.14 * raw_stressor)
            p["chronic_days"] = max(0, p["chronic_days"] - 1)
        else:
            excess = (raw_stressor - tol) / max(0.15, 1.0 - tol)
            p["anger"] = clamp(p["anger"] * cfg["anger_retention"] + 0.48 * clamp(excess) + 0.15 * raw_stressor)
            p["chronic_days"] += 1

    # 5. Forced compliance / fear -> Repressed anger + Pluralistic Ignorance & Focal Break
    compliance_gap = max(0.0, public_support - private_loyalty)
    silenced = p["fear"] >= 0.30 or compliance_gap >= 0.20
    if p["anger"] > 0.18 and silenced:
        transfer = 0.28 * p["anger"] * clamp(max(p["fear"], compliance_gap))
        p["repressed_anger"] = clamp(p["repressed_anger"] * cfg["repressed_retention"] + transfer)
    else:
        p["repressed_anger"] = clamp(p["repressed_anger"] * cfg["repressed_retention"])

    common_knowledge_surge = 0.0
    if use_v2 and group != "observer":
        silent_nb = float(sctx.get("silent_ratio", 0.0))
        if leak_signal:
            # Public leak shatters pluralistic ignorance simultaneously!
            common_knowledge_surge = 0.32 * p["pluralistic_ignorance"]
            p["pluralistic_ignorance"] = clamp(p["pluralistic_ignorance"] * 0.12)
        elif (p["anger"] > 0.22 or raw_stressor > tol) and silent_nb >= 0.50:
            p["pluralistic_ignorance"] = clamp(0.76 * p["pluralistic_ignorance"] + 0.32 * silent_nb)
        else:
            p["pluralistic_ignorance"] = clamp(0.80 * p["pluralistic_ignorance"])

    release_bonus = 0.0
    if p["repressed_anger"] > 0.15 and (leak_signal or (p["fear"] < 0.25 and p["defense_wall"] < 0.40)):
        release_bonus = 0.55 * p["repressed_anger"] + common_knowledge_surge
        p["repressed_anger"] = clamp(p["repressed_anger"] * 0.72)
    elif common_knowledge_surge > 0:
        release_bonus = common_knowledge_surge

    # 6. Exhaustion with Resource-Bounded Solidarity Capacity (fixes infinite Day-40 immunity)
    if use_v2:
        sol_cap = clamp(float(sctx.get("solidarity_capacity", 1.0)) * (1.0 - 0.45 * clamp(harm + income_harm)), 0.15, 1.0)
        p["solidarity_capacity"] = round(sol_cap, 4)
        if raw_stressor > tol and p["chronic_days"] >= 3:
            if not collective_supported:
                step_mult = 1.0
            elif p["chronic_days"] >= 5:
                # Solidarity slows burnout significantly, but depleted neighborhoods still tire!
                step_mult = 0.26 + 0.48 * (1.0 - sol_cap)
            else:
                step_mult = 0.0
            p["exhaustion"] = clamp(p["exhaustion"] + step_mult * cfg["exhaustion_step"] * exh_rate * (0.5 + 0.5 * raw_stressor))
        else:
            recovery = cfg["exhaustion_recovery"] * (0.90 if collective_supported else 1.0)
            p["exhaustion"] = clamp(p["exhaustion"] * recovery)
    else:
        if raw_stressor > tol and p["chronic_days"] >= 3 and not collective_supported:
            p["exhaustion"] = clamp(p["exhaustion"] + cfg["exhaustion_step"] * exh_rate * (0.5 + 0.5 * raw_stressor))
        else:
            recovery = cfg["exhaustion_recovery"] * (0.90 if collective_supported else 1.0)
            p["exhaustion"] = clamp(p["exhaustion"] * recovery)

    # 7. Silent Disengagement ('Küskün Seçmen') & Observer Epistemic Whistleblowing
    if use_v2:
        if alignment in ("A", "B") and group in ("power_aligned", "opposition"):
            if p["defense_wall"] < 0.42 and (p["comfort"] < 0.34 or p["role_dissonance"] >= 0.34 or p["exhaustion"] >= 0.48):
                p["disengaged"] = True
            elif p["defense_wall"] >= 0.52 and p["comfort"] >= 0.45 and p["role_dissonance"] < 0.20:
                p["disengaged"] = False
        if group == "observer":
            contrad = max(max_own_error, float(sctx.get("contradiction_spread", 0.0)))
            evidence_pulse = 0.46 * coverup_signal + 0.34 * disruption_level + 0.25 * contrad + (0.20 if leak_signal else 0.0)
            if evidence_pulse > 0.18:
                p["epistemic_alarm"] = clamp(0.76 * p["epistemic_alarm"] + 0.45 * evidence_pulse)
            else:
                p["epistemic_alarm"] = clamp(0.82 * p["epistemic_alarm"])
            p["whistleblower_ready"] = bool(p["epistemic_alarm"] >= 0.62 and p["fear"] < 0.72)

    expr, dom = _classify_expression_and_dominant(
        group, subwing, tol, raw_stressor, p["comfort"], p["fear"],
        p["anger"], p["repressed_anger"], p["exhaustion"], p["defense_wall"],
        use_v2=use_v2, p=p,
    )
    p["expression_mode"] = expr
    p["dominant_state"] = dom

    # Effective action drive: shaped by exhaustion, comfort, pluralistic ignorance, disengagement, or observer alarm
    if expr == "self_censored":
        p["effective_drive"] = 0.0
    elif group == "observer":
        p["effective_drive"] = round(0.35 * p["epistemic_alarm"], 4) if (use_v2 and p["whistleblower_ready"]) else 0.0
    else:
        raw_drive = clamp(p["anger"] + release_bonus)
        damping = (1.0 - 0.72 * p["exhaustion"]) * (1.0 - 0.30 * p["comfort"])
        if use_v2:
            damping *= (1.0 - 0.42 * p["pluralistic_ignorance"])
            if p["disengaged"]:
                damping *= 0.35
        if expr == "guarded":
            damping *= 0.65
        p["effective_drive"] = clamp(raw_drive * damping)
    return p


def apply_stimulus(sim, a, kind: str, magnitude: float = 0.5, cause=None):
    """Immediate local stimulus from direct pressure or contract revocation."""
    if not enabled(sim):
        return
    p = state(a)
    fear_sens = a.traits.get("fear_sensitivity", 0.4)
    if kind == "pressure":
        p["fear"] = clamp(p["fear"] + 0.48 * magnitude * (0.5 + fear_sens))
        compliance_gap = max(0.0, a.public_support - a.private_loyalty)
        if compliance_gap > 0.15 or p["anger"] > 0.15:
            p["repressed_anger"] = clamp(p["repressed_anger"] + 0.25 * max(compliance_gap, p["anger"]))
    elif kind == "contract_loss":
        p["fear"] = clamp(p["fear"] + 0.55 * magnitude * (0.5 + fear_sens))
        p["comfort"] = clamp(p["comfort"] - 0.35 * magnitude)
        p["anger"] = clamp(p["anger"] + 0.30 * magnitude * a.traits.get("economic_harm_response", 0.5))
    expr, dom = _classify_expression_and_dominant(
        a.initial_group, p.get("subwing"), p["tolerance_threshold"], p["stressor"],
        p["comfort"], p["fear"], p["anger"], p["repressed_anger"], p["exhaustion"], p["defense_wall"],
        use_v2=v2_enabled(sim), p=p,
    )
    p["expression_mode"] = expr
    p["dominant_state"] = dom
    sim.record("psychology_stimulus", {
        "agent": a.id, "stimulus": kind, "fear": p["fear"],
        "repressed_anger": p["repressed_anger"], "expression_mode": expr,
    }, cause)


def trust_erosion_multiplier(sim, a) -> float:
    """Defense wall & intermediary blame-shifting buffer early failures; broken wall amplifies disillusionment."""
    if not enabled(sim):
        return 1.0
    p = state(a)
    wall = p["defense_wall"]
    if v2_enabled(sim) and p.get("blame_shifted"):
        return 0.28
    if wall >= 0.45:
        return 1.0 - 0.55 * wall
    if wall < 0.30:
        return 1.15
    return 1.0


def daily(sim, a, harm: float, income_harm: float, disruption_level: float,
          responsibility_own: float, max_own_error: float, collective_supported: bool, cause=None):
    if not enabled(sim):
        return None
    p = state(a)
    cfg = sim.behavior_profile["psychology_dynamics"]
    use_v2 = v2_enabled(sim)
    sctx = _local_social_context(sim, a) if use_v2 else None
    _step_agent_psychology(
        p, a.traits, a.initial_group, a.alignment, a.public_support, a.private_loyalty,
        a.pressure, cfg, harm, income_harm, disruption_level,
        responsibility_own, max_own_error, collective_supported,
        use_v2=use_v2, social_ctx=sctx,
    )
    if use_v2 and p.get("disengaged") and a.public_support > 0.40:
        # Küskün seçmen kutbunu terk etmez ama aktif görünür desteğini sessizce geri çeker.
        a.public_support = round(max(0.38, a.public_support - 0.04), 4)
    sim.record("psychology_updated", {
        "agent": a.id, "comfort": p["comfort"], "fear": p["fear"],
        "anger": p["anger"], "repressed_anger": p["repressed_anger"],
        "exhaustion": p["exhaustion"], "defense_wall": p["defense_wall"],
        "expression_mode": p["expression_mode"], "dominant_state": p["dominant_state"],
        "effective_drive": p["effective_drive"],
    }, cause)
    return p


def expression_for_agenda(sim, a, approach: str) -> str:
    """Fear, disengagement and exhaustion shape outer speech tone without altering belief."""
    group = a.initial_group
    if group in ("authority", "wealthy"):
        if enabled(sim):
            p = state(a)
            if p["expression_mode"] == "self_censored":
                return "self_censored_silence"
            if p["expression_mode"] == "guarded":
                return "guarded_interest_assessment"
        return "private_interest_assessment"
    if group == "observer":
        if v2_enabled(sim) and state(a).get("whistleblower_ready"):
            return "epistemic_technical_warning"
        return "reserved_observation"
    if enabled(sim):
        p = state(a)
        if p["expression_mode"] == "self_censored":
            return "self_censored_silence"
        if p["expression_mode"] == "disengaged_silence":
            return "disengaged_" + approach
        if p["expression_mode"] == "exhausted_withdrawal":
            return "exhausted_" + approach
        if p["expression_mode"] == "guarded":
            return "guarded_" + approach
    if a.traits["risk_tolerance"] < 1 - a.traits["pressure_response"]:
        return "private_" + approach
    return approach


def _scenario_day_signals(tier: str, domain: str, cond: dict, day_no: int):
    """Map non-numeric causal conditions of a scenario day to bounded environmental signals."""
    fear_map = {"low": 0.05, "elevated": 0.45, "high": 0.82}
    coverup_map = {"none": 0.05, "moderate": 0.42, "high": 0.78}
    threat = fear_map.get(cond.get("prosecution_fear", "low"), 0.05)
    coverup = coverup_map.get(cond.get("coverup_level", "none"), 0.05)
    leak = bool(cond.get("leak_occurred"))
    scapegoat = bool(cond.get("scapegoat_isolated"))
    neglect = bool(cond.get("unaddressed_neglect"))

    if tier == "ordinary":
        harm, disruption, resp_A = 0.04, 0.08, 0.15
    elif tier == "institutional_crisis":
        harm = 0.45 if domain == "economic_crisis" else 0.25
        disruption = 0.35 + (0.15 if leak else 0.0)
        resp_A = 0.55 + (0.20 if leak else 0.0) - (0.12 if scapegoat else 0.0)
    else:  # severe safety / disaster / armed crisis
        harm = 0.40 + (0.20 if neglect else 0.0)
        disruption = 0.65 + (0.20 if cond.get("aftershock_stage") == "aftershock_occurred" else 0.0)
        if not neglect and day_no >= 8:
            disruption = 0.35
        resp_A = 0.60 + (0.22 if leak else 0.0) - (0.10 if scapegoat else 0.0)
    return {
        "harm": clamp(harm),
        "disruption": clamp(disruption),
        "threat": clamp(threat),
        "coverup": clamp(coverup),
        "leak": leak,
        "scapegoat": scapegoat,
        "resp_A": clamp(resp_A),
    }


def _describe_group_psychology_tr(gid: str, stats: dict) -> str:
    dom = stats["baskin_durum"]
    korku = stats["korku"]
    ofke = stats["ofke"]
    bastirilmis = stats["bastirilmis_ofke"]
    konfor = stats["konfor"]
    tukenmislik = stats["tukenmislik"]
    savunma = stats["savunma"]
    asan = stats["esik_asan_oran"]
    kuskun = stats.get("kuskun_oran", 0)
    araci = stats.get("araci_guveni", 75)
    cehalet = stats.get("cogulcu_cehalet", 0)
    yoksunluk = stats.get("goreli_yoksunluk", 0)
    alarm = stats.get("epistemik_alarm", 0)

    if gid == "power_aligned":
        if kuskun >= 20:
            return (f"Aracı kurum güveni (%{araci}) ve savunma duvarı (%{savunma}) aşındı; "
                    f"karşı kutba geçmeden kitlenin %{kuskun}'i 'küskün/sessiz kopuş' evresine girdi.")
        if dom == "suc_kaydirma" or (savunma >= 55 and araci < 58):
            return (f"Çekirdek lidere bağlılık korunuyor (Savunma %{savunma}) ancak suçu bürokrasi ve "
                    f"aracılara kaydırma refleksi devrede (Aracı güveni %{araci}).")
        if savunma >= 55 and asan < 40:
            return (f"Savunma duvarı (%{savunma}) ve düzen konforu (%{konfor}) yüksek; "
                    f"sorumluluğu üst yönetim yerine münferit/dış etkenlere bağlayarak rasyonalize ediyor.")
        return (f"Kişisel zarar ve çelişkiler savunma duvarını (%{savunma}) aşındırdı; "
                f"kitlenin %{asan}'inde sabır eşiği aşıldı, açık kavgaya girmeden sessiz kırgınlık başlıyor.")
    if gid == "opposition":
        if cehalet >= 38:
            return (f"Çevredeki sessizlik yüzünden çoğulcu cehalet (%{cehalet}) yükseldi; bireyler "
                    f"'yalnız mıyım?' kaygısıyla imalı dile çekilirken içeride %{bastirilmis} tepki birikiyor.")
        if dom in ("korku_otosansur", "bastirilmis_ofke") or korku >= 40:
            return (f"İçsel itiraz sürüyor (Öfke %{ofke}) ancak korku (%{korku}) yükseldiği için "
                    f"açık çağrıdan imalı dile geçildi; bastırılmış tepki (%{bastirilmis}) içeride birikiyor.")
        return (f"Tahammül eşiği düşük olduğu için %{asan} kesimde aktif itiraz uyanık; "
                f"usul ve denetim eksikliğini açıkça sorguluyor.")
    if gid == "authority":
        return (f"Koltuk ve düzen konforu (%{konfor}) öncelikli; kurumsal güç kaybı kaygısı (%{korku}) "
                f"nedeniyle kontrol/günah keçisi refleksi baskın, küçük iç azınlıkta örtbas huzursuzluğu var.")
    if gid == "wealthy":
        subs = stats.get("alt_kanatlar", {})
        nt = subs.get("neutral_commercial", {})
        nk = nt.get("korku", korku)
        if nk >= 40:
            return (f"A kanadı algıyı yumuşatıp B kanadı risk sınırı kollarken, Tarafsız/Ticari kanatta "
                    f"suçlanma korkusu (%{nk}) eşiği aştı ve otosansür devreye girdi.")
        return (f"Konfor ve ticari istikrar (%{konfor}) korunuyor; 3 alt kanat kendi çıkar ve kutup "
                f"dengesine göre kontrollü pozisyon alıyor.")
    if gid == "discontented":
        if dom == "tukenmislik" or tukenmislik >= 50:
            return (f"Uzayan çözümsüzlük ve eriyen dayanışma gücü aktif öfkeyi (%{ofke}) tükenmişliğe (%{tukenmislik}) "
                    f"çevirdi; partizanlığa geçmeden derin güvensizlik ve yorgun kabulleniş birikiyor.")
        extra = f" Görünür imtiyaz uçurumu (%{yoksunluk}) adalet öfkesini katlıyor." if yoksunluk >= 20 else ""
        return (f"Başlangıç konforu düşük (%{konfor}); kitlenin %{asan}'inde sabır eşiği kırıldı, "
                f"öfke (%{ofke}) ve yerel boykot/itiraz arayışı yükseliyor.{extra}")
    if alarm >= 60:
        return (f"İki kutuptan toplanan çelişkiler epistemik alarm eşiğini (%{alarm}) aştı; "
                f"yaklaşan ikincil riske karşı kanıta dayalı 'Teknik Uyarı' konumuna geçti.")
    return (f"Propaganda ve sürü etkisine kapalı (Konfor/Mesafe %{konfor}, Korku %{korku}); "
            f"yöneticilerin örtbas ve medyanın algı tiyatrosunu dışarıdan soğukkanlılıkla çözümlüyor.")


def _aggregate_records(records):
    if not records:
        return None
    n = len(records)
    avg = lambda k, default=0.0: round(sum(float(r.get(k, default)) for r in records) / n * 100)
    dom = Counter(r["dominant_state"] for r in records).most_common(1)[0][0]
    expr = Counter(r["expression_mode"] for r in records).most_common(1)[0][0]
    breached = round(sum(1 for r in records if r["stressor"] > r["tolerance_threshold"]) / n * 100)
    disengaged_pct = round(sum(1 for r in records if r.get("disengaged")) / n * 100)
    blame_shift_pct = round(sum(1 for r in records if r.get("blame_shifted")) / n * 100)
    wb_pct = round(sum(1 for r in records if r.get("whistleblower_ready")) / n * 100)
    return {
        "kisi": n,
        "tahammul_esigi": avg("tolerance_threshold"),
        "konfor": avg("comfort"),
        "korku": avg("fear"),
        "ofke": avg("anger"),
        "bastirilmis_ofke": avg("repressed_anger"),
        "tukenmislik": avg("exhaustion"),
        "savunma": avg("defense_wall"),
        "eylem_itkisi": avg("effective_drive"),
        "araci_guveni": avg("intermediary_trust", 0.65),
        "rol_celiskisi": avg("role_dissonance"),
        "cogulcu_cehalet": avg("pluralistic_ignorance"),
        "goreli_yoksunluk": avg("relative_deprivation"),
        "dayanisma_kapasitesi": avg("solidarity_capacity", 1.0),
        "epistemik_alarm": avg("epistemic_alarm"),
        "kuskun_oran": disengaged_pct,
        "suc_kaydirma_oran": blame_shift_pct,
        "uyari_hazir_oran": wb_pct,
        "esik_asan_oran": breached,
        "ifade_modu": expr,
        "ifade_etiketi": EXPRESSION_LABELS_TR.get(expr, expr),
        "baskin_durum": dom,
        "baskin_etiket": DOMINANT_LABELS_TR.get(dom, dom),
    }


def group_summary(sim, chain: dict | None = None, upto_day: int | None = None) -> dict:
    """Compute 6-group (plus 3 wealthy subwings) psychological state without mutating sim."""
    if chain and chain.get("day", 0) > 0:
        history = chain.get("history", [])
        target_day = upto_day if upto_day is not None else chain.get("day", 1)
        exact = next((h for h in reversed(history)
                      if h.get("day") == target_day and isinstance(h.get("psychology_snapshot"), dict)), None)
        if exact is not None:
            return deepcopy(exact["psychology_snapshot"])

    cfg = sim.behavior_profile.get("psychology_dynamics") or {
        "fear_retention": 0.88, "anger_retention": 0.82, "repressed_retention": 0.97,
        "comfort_recovery": 0.08, "defense_erosion": 0.14, "defense_recovery": 0.03,
        "exhaustion_step": 0.09, "exhaustion_recovery": 0.92, "peer_pull_retention": 0.92,
    }
    use_v2 = v2_enabled(sim)
    projected = {}
    w_idx = 0
    for a in sim.agents.values():
        if "psychology" in a.behavior:
            base = deepcopy(a.behavior["psychology"])
        else:
            comfort0 = _default_trait(a, "comfort_baseline", 0.5)
            defense0 = _default_trait(a, "defense_strength", 0.5)
            tol0 = _default_trait(a, "tolerance_threshold", 0.5)
            default_dom = "sogukkanli_gozlem" if a.initial_group == "observer" else (
                "konfor_koruma" if comfort0 >= 0.55 else "sabir_esiginde")
            base = {
                "tolerance_threshold": tol0, "comfort": comfort0, "fear": 0.0,
                "anger": 0.0, "repressed_anger": 0.0, "exhaustion": 0.0,
                "defense_wall": defense0, "chronic_days": 0, "stressor": 0.0,
                "effective_drive": 0.0, "expression_mode": "open",
                "dominant_state": default_dom, "subwing": a.behavior.get("subwing"),
                "conscience_insider": False,
            }
        if a.initial_group == "wealthy" and not base.get("subwing"):
            base["subwing"] = wealthy_subwing(w_idx)
            w_idx += 1
        _ensure_v2_fields(base, a.initial_group)
        projected[a.id] = (a, base)

    if chain and chain.get("day", 0) > 0:
        tier = chain.get("tier", "ordinary")
        domain = chain.get("domain", "ordinary")
        history = chain.get("history", [])
        synced_day = int(chain.get("synced_day", 0) or 0)
        target_day = upto_day if upto_day is not None else chain.get("day", 1)
        steps = [h for h in history if isinstance(h.get("day"), int) and synced_day < h["day"] <= target_day]
        if not steps and target_day > synced_day:
            steps = [{"day": d, "conditions": chain.get("conditions", {})}
                     for d in range(synced_day + 1, target_day + 1)]
        for step in steps:
            dno = step.get("day", 1)
            cond = step.get("conditions") or chain.get("conditions", {})
            sig = _scenario_day_signals(tier, domain, cond, dno)
            silent_env = 0.65 if sig["threat"] >= 0.45 and not sig["leak"] else 0.15
            for a, p in projected.values():
                own_resp = sig["resp_A"] if a.alignment == "A" else (0.15 if a.alignment == "B" else 0.0)
                own_err = (0.45 if sig["leak"] else 0.20 * sig["harm"]) if a.alignment == "A" else 0.0
                subwing = p.get("subwing")
                role_threat = sig["threat"]
                inc_harm = 0.0
                if a.initial_group == "wealthy":
                    if subwing == "pro_A":
                        role_threat = sig["threat"] * 0.35
                        inc_harm = 0.06 * sig["threat"]
                    elif subwing == "pro_B":
                        role_threat = sig["threat"] * 0.92
                        inc_harm = 0.22 * sig["threat"]
                    else:  # neutral_commercial
                        role_threat = clamp(sig["threat"] * 1.15)
                        inc_harm = 0.32 * sig["threat"]
                elif a.initial_group == "authority":
                    role_threat = clamp(sig["threat"] * 0.55 + (0.30 if sig["scapegoat"] else 0.0))
                elif a.initial_group == "opposition":
                    role_threat = sig["threat"] * 0.85
                elif a.initial_group == "discontented":
                    role_threat = sig["threat"] * 0.60
                elif a.initial_group == "power_aligned":
                    role_threat = sig["threat"] * 0.25
                else:  # observer
                    role_threat = sig["threat"] * 0.20
                sctx = {
                    "silent_ratio": silent_env,
                    "neighbor_fear": role_threat * 0.6,
                    "neighbor_anger": sig["harm"] * 0.5,
                    "solidarity_capacity": max(0.25, 1.0 - 0.5 * sig["harm"]),
                    "elite_comfort": 0.74 if sig["coverup"] >= 0.40 else 0.55,
                    "contradiction_spread": 0.35 if sig["coverup"] >= 0.40 else 0.10,
                } if use_v2 else None
                _step_agent_psychology(
                    p, a.traits, a.initial_group, a.alignment, a.public_support, a.private_loyalty,
                    a.pressure, cfg,
                    harm=sig["harm"],
                    income_harm=inc_harm,
                    disruption_level=sig["disruption"],
                    responsibility_own=own_resp,
                    max_own_error=own_err,
                    collective_supported=(a.initial_group == "discontented" and dno in (5, 6) and tier != "ordinary"),
                    threat_signal=role_threat,
                    coverup_signal=sig["coverup"],
                    leak_signal=sig["leak"],
                    use_v2=use_v2,
                    social_ctx=sctx,
                )

    by_group = {}
    for gid in ("power_aligned", "opposition", "authority", "wealthy", "discontented", "observer"):
        items = [(a, p) for a, p in projected.values() if a.initial_group == gid]
        agg = _aggregate_records([p for _, p in items]) or {}
        if gid == "wealthy":
            sub_map = {}
            for sw in WEALTHY_SUBWINGS:
                sw_records = [p for _, p in items if p.get("subwing") == sw]
                if sw_records:
                    sw_agg = _aggregate_records(sw_records)
                    sw_agg["ad"] = SUBWING_LABELS_TR[sw]
                    sub_map[sw] = sw_agg
            agg["alt_kanatlar"] = sub_map
        if gid == "authority":
            insiders = [p for _, p in items if p.get("conscience_insider")]
            agg["ic_catlak_sayisi"] = len(insiders)
            agg["ic_sizinti_egilimi"] = round(sum(p["anger"] + p["repressed_anger"] for p in insiders) / len(insiders) * 100) if insiders else 0
        agg["yorum"] = _describe_group_psychology_tr(gid, agg) if agg else ""
        by_group[gid] = agg
    return by_group


def social_mind_overview(psych_by_role: dict) -> dict:
    """High-level macro-psychological indicators across all 6 groups for operator & UI radar."""
    if not psych_by_role:
        return {}
    pa = psych_by_role.get("power_aligned", {})
    op = psych_by_role.get("opposition", {})
    au = psych_by_role.get("authority", {})
    we = psych_by_role.get("wealthy", {})
    di = psych_by_role.get("discontented", {})
    ob = psych_by_role.get("observer", {})
    nt = (we.get("alt_kanatlar") or {}).get("neutral_commercial", {})

    kuskun_toplam = round((pa.get("kuskun_oran", 0) * 0.30 + op.get("kuskun_oran", 0) * 0.30) / 0.60)
    sahte_huzur = round(max(op.get("cogulcu_cehalet", 0), op.get("bastirilmis_ofke", 0), nt.get("korku", 0)))
    patlama_potansiyeli = round(
        0.38 * di.get("ofke", 0)
        + 0.32 * op.get("bastirilmis_ofke", 0)
        + 0.30 * di.get("goreli_yoksunluk", 0)
    )
    return {
        "kuskun_secmen_orani": kuskun_toplam,
        "iktidar_araci_guveni": pa.get("araci_guveni", 75),
        "iktidar_suc_kaydirma": pa.get("suc_kaydirma_oran", 0),
        "muhalif_cogulcu_cehalet": op.get("cogulcu_cehalet", 0),
        "goreli_yoksunluk": di.get("goreli_yoksunluk", 0),
        "dayanisma_kapasitesi": di.get("dayanisma_kapasitesi", 100),
        "gozlemci_epistemik_alarm": ob.get("epistemik_alarm", 0),
        "gozlemci_uyari_hazir": ob.get("uyari_hazir_oran", 0) > 0,
        "tarafsiz_medya_korku": nt.get("korku", we.get("korku", 0)),
        "ic_sizinti_egilimi": au.get("ic_sizinti_egilimi", 0),
        "sahte_uyum_riski": min(100, sahte_huzur),
        "yay_bosalma_potansiyeli": min(100, patlama_potansiyeli),
    }


def institutional_memory_state(sim) -> dict:
    return sim.protocol.setdefault("institutional_memory", {
        "past_crises": 0,
        "coverup_scar": 0.0,
        "scapegoat_scar": 0.0,
        "reform_credit": 0.0,
        "episodes": [],
    })


def imprint_institutional_memory(sim, closed_chain: dict | None) -> dict:
    """Kapanan krizin örtbas/günah keçisi veya şeffaf onarım izini kitle hafızasına kazır."""
    mem = institutional_memory_state(sim)
    if not closed_chain or closed_chain.get("day", 0) < 2 or closed_chain.get("tier") == "ordinary":
        return mem
    if closed_chain.get("memory_imprinted"):
        return mem
    closed_chain["memory_imprinted"] = True

    cond = closed_chain.get("conditions", {})
    bstate = closed_chain.get("branch_state", {})
    reformed = bool(bstate.get("reform_credibility", 0) >= 6 and not cond.get("scapegoat_isolated"))
    had_coverup = cond.get("coverup_level") == "high" or bool(cond.get("leak_occurred"))
    had_scapegoat = bool(cond.get("scapegoat_isolated"))
    had_aftershock = cond.get("aftershock_stage") == "aftershock_occurred"

    mem["past_crises"] += 1
    if reformed:
        mem["reform_credit"] = round(clamp(mem["reform_credit"] + 0.18), 4)
        mem["coverup_scar"] = round(clamp(mem["coverup_scar"] - 0.08), 4)
        outcome_label = "seffaf_onarim"
    else:
        c_delta = (0.16 if had_coverup else 0.08) + (0.08 if had_aftershock else 0.0)
        s_delta = 0.20 if had_scapegoat else 0.0
        mem["coverup_scar"] = round(clamp(mem["coverup_scar"] + c_delta), 4)
        mem["scapegoat_scar"] = round(clamp(mem["scapegoat_scar"] + s_delta), 4)
        outcome_label = "gunah_kecisi_ve_ortbas" if had_scapegoat else "cozumsuz_ortbas"

    if enabled(sim):
        for a in sim.agents.values():
            p = state(a)
            if reformed:
                base_tol = float(a.initial_traits.get("tolerance_threshold", p["tolerance_threshold"]))
                p["tolerance_threshold"] = clamp(p["tolerance_threshold"] + 0.35 * (base_tol - p["tolerance_threshold"]))
                p["exhaustion"] = clamp(p["exhaustion"] * 0.72)
                p["disengaged"] = False
            else:
                if a.initial_group in ("opposition", "discontented"):
                    drop = 0.06 + (0.03 if had_scapegoat else 0.0)
                    p["tolerance_threshold"] = max(0.08, round(p["tolerance_threshold"] - drop, 4))
                elif a.initial_group == "power_aligned":
                    erosion = 0.05 + (0.04 if had_aftershock else 0.0)
                    p["defense_wall"] = max(0.22, round(p["defense_wall"] - erosion, 4))
                    p["intermediary_trust"] = max(0.18, round(p["intermediary_trust"] - 0.10, 4))
                elif a.initial_group == "authority" and p.get("conscience_insider"):
                    p["repressed_anger"] = clamp(p["repressed_anger"] + 0.15)
                elif a.initial_group == "wealthy" and p.get("subwing") == "neutral_commercial":
                    if cond.get("detained_individuals", 0) > 0:
                        p["fear"] = max(p["fear"] * 0.60, 0.18)

    episode = {
        "index": mem["past_crises"],
        "event": str(closed_chain.get("initial_event", ""))[:160],
        "tier": closed_chain.get("tier"),
        "domain": closed_chain.get("domain"),
        "days": closed_chain.get("day", 0),
        "outcome": outcome_label,
    }
    mem["episodes"] = [*mem.get("episodes", [])[-19:], episode]
    sim.record("institutional_memory_imprinted", {
        "past_crises": mem["past_crises"],
        "outcome": outcome_label,
        "coverup_scar": mem["coverup_scar"],
        "scapegoat_scar": mem["scapegoat_scar"],
        "reform_credit": mem["reform_credit"],
    })
    return mem


def memory_summary_tr(sim) -> dict:
    mem = institutional_memory_state(sim)
    n = mem["past_crises"]
    c_scar = round(mem["coverup_scar"] * 100)
    s_scar = round(mem["scapegoat_scar"] * 100)
    r_cred = round(mem["reform_credit"] * 100)
    if n == 0:
        yorum = "Henüz kapanmış geçmiş kriz yok; kitleler başlangıç tahammül ve savunma eşiklerinde."
    elif c_scar >= 20 or s_scar >= 20:
        yorum = (f"Toplumsal hafızada {n} geçmiş kriz kayıtlı (Örtbas izi %{c_scar}, Günah keçisi izi %{s_scar}): "
                 f"muhalif ve hoşnutsuzlarda sabır eşiği düştü, içeride sızıntı eğilimi arttı, savunma duvarı inceldi.")
    else:
        yorum = (f"Toplumsal hafızada {n} geçmiş kriz kayıtlı (Şeffaf onarım kredisi %{r_cred}): "
                 f"erken kurumsal müdahale toplumsal güven aşınmasını sınırladı.")
    return {
        "gecmis_kriz_sayisi": n,
        "ortbas_izi": c_scar,
        "gunah_kecisi_izi": s_scar,
        "onarim_kredisi": r_cred,
        "son_krizler": deepcopy(mem.get("episodes", [])[-5:]),
        "yorum": yorum,
    }
