"""v3.4 Psikolojik Derinlik ve Sosyal Dinamikler Deney Paketi.

6 ayrı çok-tohumlu (multi-seed) deney ve N=1000 ölçek doğrulaması çalıştırır;
sayısal bulguları `reports/psychology-research-v34.json` dosyasına kaydeder.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from statistics import mean

from . import behavior, psychology, termux
from .agenda import ReferenceAdvisor
from .engine import BaselineProvider, Config, Simulation


def _round(v, d=4):
    return round(float(v), d) if v is not None else None


def _group_means(sim, group):
    ags = [a for a in sim.agents.values() if a.initial_group == group]
    if not ags:
        return {}
    has_p = "psychology" in ags[0].behavior
    own_trusts = []
    for a in ags:
        known = a.behavior.get("known", {})
        tr = [v for k, v in a.behavior.get("trust", {}).items() if known.get(k, {}).get("pole") == a.alignment]
        if tr:
            own_trusts.append(mean(tr))
    out = {
        "count": len(ags),
        "private_loyalty": _round(mean(a.private_loyalty for a in ags)),
        "public_support": _round(mean(a.public_support for a in ags)),
        "support_gap": _round(mean(abs(a.public_support - a.private_loyalty) for a in ags)),
        "own_pole_trust": _round(mean(own_trusts)) if own_trusts else None,
        "losses": _round(mean(a.losses for a in ags)),
        "switches": sum(a.behavior.get("switch_count", 0) for a in ags),
    }
    if has_p:
        ps = [a.behavior["psychology"] for a in ags]
        out.update({
            "comfort": _round(mean(p["comfort"] for p in ps)),
            "fear": _round(mean(p["fear"] for p in ps)),
            "anger": _round(mean(p["anger"] for p in ps)),
            "repressed_anger": _round(mean(p["repressed_anger"] for p in ps)),
            "exhaustion": _round(mean(p["exhaustion"] for p in ps)),
            "defense_wall": _round(mean(p["defense_wall"] for p in ps)),
            "tolerance_threshold": _round(mean(p["tolerance_threshold"] for p in ps)),
            "effective_drive": _round(mean(p["effective_drive"] for p in ps)),
            "self_censored_ratio": _round(sum(1 for p in ps if p["expression_mode"] == "self_censored") / len(ps)),
            "guarded_ratio": _round(sum(1 for p in ps if p["expression_mode"] == "guarded") / len(ps)),
        })
    return out


def exp1_v33_vs_v34_and_scale(seeds=(44, 101, 202)):
    """Deney 1: v3.3 vs v3.4 karşılaştırması, yankı odası indeksi ve N=1000 ölçek testi."""
    def run_one(profile, seed, pop=100, days=25):
        sim = Simulation(Config(population=pop, seed=seed), behavior_profile=profile)
        sim.run(0, BaselineProvider())
        # Gün 1: A otoritesi iyimser ekonomik tahmin yayar, ardından fiyat şoku gelir
        leaders_a = [a.id for a in sim.agents.values() if a.initial_group == "authority" and a.alignment == "A"]
        if leaders_a:
            la = leaders_a[0]
            targets = [e["target"] for e in sim.edges if e["source"] == la][:12]
            for idx, tid in enumerate(targets):
                sim.schedule(10 + idx, "external_action", {
                    "actor": la,
                    "proposal": {"type": "send", "target": tid, "topic": "economic_outlook", "claim": 5, "text": "Fiyatlar sabit kalacak."},
                })
        sim.schedule(120, "price_shock", {"multiplier": 1.65})
        sim.run(days * 1440 - 1, BaselineProvider())

        # Yankı odası homofili oranı (power_aligned + opposition yakın bağları)
        same = total = 0
        for e in sim.edges:
            if e["type"] == "close":
                sa, ta = sim.agents[e["source"]], sim.agents[e["target"]]
                if sa.initial_group in ("power_aligned", "opposition"):
                    total += 1
                    if sa.alignment == ta.alignment:
                        same += 1
        # Gözlemcilerin gelen izleme çeşitliliği
        obs_in = [len([e for e in sim.edges if e["target"] == a.id])
                  for a in sim.agents.values() if a.initial_group == "observer"]
        return {
            "homophily_ratio": _round(same / max(1, total)),
            "observer_avg_incoming_links": _round(mean(obs_in)),
            "world": {k: _round(v) if isinstance(v, float) else v for k, v in sim.behavior_metrics().items()},
            "groups": {g: _group_means(sim, g) for g in ("power_aligned", "opposition", "authority", "wealthy", "discontented", "observer")},
        }

    v33 = behavior.load_v33_profile()
    v34 = behavior.load_v34_profile()
    runs_v33 = [run_one(v33, s, pop=100, days=25) for s in seeds]
    runs_v34 = [run_one(v34, s, pop=100, days=25) for s in seeds]
    scale_1000 = run_one(v34, 44, pop=1000, days=15)

    return {
        "v33_mean_100": {
            "homophily_ratio": _round(mean(r["homophily_ratio"] for r in runs_v33)),
            "observer_avg_incoming_links": _round(mean(r["observer_avg_incoming_links"] for r in runs_v33)),
            "alignment_changes": _round(mean(r["world"]["alignment_changes"] for r in runs_v33)),
            "mean_trust": _round(mean(r["world"]["mean_trust"] for r in runs_v33)),
            "power_aligned_trust": _round(mean(r["groups"]["power_aligned"]["own_pole_trust"] for r in runs_v33)),
            "opposition_loyalty": _round(mean(r["groups"]["opposition"]["private_loyalty"] for r in runs_v33)),
        },
        "v34_mean_100": {
            "homophily_ratio": _round(mean(r["homophily_ratio"] for r in runs_v34)),
            "observer_avg_incoming_links": _round(mean(r["observer_avg_incoming_links"] for r in runs_v34)),
            "alignment_changes": _round(mean(r["world"]["alignment_changes"] for r in runs_v34)),
            "mean_trust": _round(mean(r["world"]["mean_trust"] for r in runs_v34)),
            "power_aligned_trust": _round(mean(r["groups"]["power_aligned"]["own_pole_trust"] for r in runs_v34)),
            "power_aligned_defense": _round(mean(r["groups"]["power_aligned"]["defense_wall"] for r in runs_v34)),
            "discontented_anger": _round(mean(r["groups"]["discontented"]["anger"] for r in runs_v34)),
            "observer_fear": _round(mean(r["groups"]["observer"]["fear"] for r in runs_v34)),
        },
        "v34_scale_1000_day15": {
            "homophily_ratio": scale_1000["homophily_ratio"],
            "observer_avg_incoming_links": scale_1000["observer_avg_incoming_links"],
            "world": scale_1000["world"],
            "power_aligned": scale_1000["groups"]["power_aligned"],
            "wealthy": scale_1000["groups"]["wealthy"],
            "discontented": scale_1000["groups"]["discontented"],
            "observer": scale_1000["groups"]["observer"],
        },
    }


def exp2_preference_falsification_and_rebound(seeds=(44, 77, 131)):
    """Deney 2: Tercih çarpıtması (ikiyüzlü uyum), tarafsız medya otosansürü ve bastırılmış öfke patlaması."""
    per_seed = []
    for seed in seeds:
        sim = Simulation(Config(population=100, seed=seed))
        sim.run(0, BaselineProvider())
        sim.schedule(30, "price_shock", {"multiplier": 1.55})
        wealthy = [a for a in sim.agents.values() if a.initial_group == "wealthy"]
        opp = [a for a in sim.agents.values() if a.initial_group == "opposition"]

        # Gün 1..10: Otorite baskısı + sözleşme sopası (Korku Sarmalı)
        for day in range(10):
            base_t = day * 1440 + 100
            for w in wealthy:
                if w.authority_dependency and w.behavior.get("subwing") in ("neutral_commercial", "pro_B"):
                    boss = sim.agents[w.authority_dependency]
                    boss.savings = max(boss.savings, 50.0)
                    sim.schedule(base_t, "external_action", {"actor": boss.id, "proposal": {"type": "pressure", "target": w.id}})
                    if day in (2, 5):
                        sim.schedule(base_t + 5, "external_action", {"actor": boss.id, "proposal": {"type": "revoke_contract", "target": w.id}})
            # Muhaliflere doğrudan baskı uyarısı
            for ag in opp[:12]:
                psychology.apply_stimulus(sim, ag, "pressure", magnitude=0.75)
                ag.public_support = min(1.0, ag.public_support + 0.18)
            sim.run((day + 1) * 1440 - 1, BaselineProvider())

        # 10. Gün sonu: "Sahte Toplumsal Huzur / İkiyüzlü Uyum" ölçümü
        wn = [w for w in wealthy if w.behavior.get("subwing") == "neutral_commercial"]
        wb = [w for w in wealthy if w.behavior.get("subwing") == "pro_B"]
        wa = [w for w in wealthy if w.behavior.get("subwing") == "pro_A"]
        repression_phase = {
            "opp_public_support": _round(mean(a.public_support for a in opp)),
            "opp_private_loyalty": _round(mean(a.private_loyalty for a in opp)),
            "opp_falsification_gap": _round(mean(a.public_support - a.private_loyalty for a in opp)),
            "opp_repressed_anger": _round(mean(a.behavior["psychology"]["repressed_anger"] for a in opp)),
            "opp_effective_drive_suppressed": _round(mean(a.behavior["psychology"]["effective_drive"] for a in opp)),
            "neutral_wealthy_self_censored": _round(sum(1 for w in wn if w.behavior["psychology"]["expression_mode"] == "self_censored") / len(wn)),
            "proB_wealthy_self_censored": _round(sum(1 for w in wb if w.behavior["psychology"]["expression_mode"] == "self_censored") / len(wb)),
            "proA_wealthy_self_censored": _round(sum(1 for w in wa if w.behavior["psychology"]["expression_mode"] == "self_censored") / len(wa)),
        }

        # Gün 11..16: Baskı kalkar + içeriden sızıntı şoku gelir -> Bastırılmış öfke boşalır!
        cfg = sim.behavior_profile["psychology_dynamics"]
        for step in range(6):
            for ag in opp:
                p = ag.behavior["psychology"]
                p["fear"] *= 0.45
                psychology._step_agent_psychology(
                    p, ag.traits, ag.initial_group, ag.alignment, ag.public_support, ag.private_loyalty,
                    0.0, cfg, harm=0.45, income_harm=0.10, disruption_level=0.25,
                    responsibility_own=0.0, max_own_error=0.0, collective_supported=True,
                    threat_signal=0.0, coverup_signal=0.55, leak_signal=(step == 0),
                )
        release_phase = {
            "opp_effective_drive_released": _round(mean(a.behavior["psychology"]["effective_drive"] for a in opp)),
            "opp_anger_after_release": _round(mean(a.behavior["psychology"]["anger"] for a in opp)),
            "opp_remaining_repressed": _round(mean(a.behavior["psychology"]["repressed_anger"] for a in opp)),
        }
        per_seed.append({"repression": repression_phase, "release": release_phase})

    return {
        "repression_phase_mean": {k: _round(mean(x["repression"][k] for x in per_seed)) for k in per_seed[0]["repression"]},
        "release_phase_mean": {k: _round(mean(x["release"][k] for x in per_seed)) for k in per_seed[0]["release"]},
    }


def exp3_coverup_vs_early_reform_branching(seeds=(44, 88, 144)):
    """Deney 3: Aynı maden faciasında 'Örtbas + Günah Keçisi' vs '2. Gün Erken Şeffaf Denetim' karşılaştırması."""
    coverup_runs, reform_runs = [], []
    for seed in seeds:
        # Kol A: Örtbas ve gecikmeli müdahale
        sim_a = termux.create_pilot(seed=seed)
        ch_a = termux.init_scenario_chain(sim_a, "Büyük maden faciası yaşandı, denetim ihmali iddiası var")
        termux.advance_scenario_days(sim_a, ReferenceAdvisor(), count=10)
        psychology.imprint_institutional_memory(sim_a, ch_a)
        ps_a = psychology.group_summary(sim_a, ch_a, upto_day=10)
        bm_a = sim_a.behavior_metrics()
        coverup_runs.append({
            "mean_trust": _round(bm_a["mean_trust"]),
            "total_losses": _round(bm_a["losses"]),
            "aftershock_occurred": any(h["conditions"].get("aftershock_stage") == "aftershock_occurred" for h in ch_a["history"]),
            "scapegoat_isolated": ch_a["conditions"]["scapegoat_isolated"],
            "peak_wealthy_fear": max(h["psychology_snapshot"]["wealthy"]["korku"] for h in ch_a["history"]),
            "day10_discontented_exhaustion": ps_a["discontented"]["tukenmislik"],
            "coverup_scar": psychology.institutional_memory_state(sim_a)["coverup_scar"],
            "max_employer_cut_workers": max(h["engine_effects"]["employer_cut_workers"] for h in ch_a["history"]),
        })

        # Kol B: 2. Günde erken şeffaf soruşturma ve somut güvenlik önlemi
        sim_b = termux.create_pilot(seed=seed)
        ch_b = termux.init_scenario_chain(sim_b, "Büyük maden faciası yaşandı, denetim ihmali iddiası var")
        termux.advance_scenario_day(sim_b, ReferenceAdvisor())
        termux.advance_scenario_day(
            sim_b, ReferenceAdvisor(),
            custom_event="Bağımsız denetim başlatıldı, sorumlu üst yönetici istifa etti ve sıkı güvenlik önlem alındı",
        )
        termux.advance_scenario_days(sim_b, ReferenceAdvisor(), count=8)
        psychology.imprint_institutional_memory(sim_b, ch_b)
        ps_b = psychology.group_summary(sim_b, ch_b, upto_day=10)
        bm_b = sim_b.behavior_metrics()
        reform_runs.append({
            "mean_trust": _round(bm_b["mean_trust"]),
            "total_losses": _round(bm_b["losses"]),
            "aftershock_occurred": any(h["conditions"].get("aftershock_stage") == "aftershock_occurred" for h in ch_b["history"]),
            "scapegoat_isolated": ch_b["conditions"]["scapegoat_isolated"],
            "peak_wealthy_fear": max(h["psychology_snapshot"]["wealthy"]["korku"] for h in ch_b["history"]),
            "day10_discontented_exhaustion": ps_b["discontented"]["tukenmislik"],
            "reform_credit": psychology.institutional_memory_state(sim_b)["reform_credit"],
            "max_employer_cut_workers": max(h["engine_effects"]["employer_cut_workers"] for h in ch_b["history"]),
        })

    return {
        "coverup_scapegoat_arm": {
            "mean_trust": _round(mean(r["mean_trust"] for r in coverup_runs)),
            "total_losses": _round(mean(r["total_losses"] for r in coverup_runs)),
            "aftershock_rate": _round(mean(1.0 if r["aftershock_occurred"] else 0.0 for r in coverup_runs)),
            "peak_wealthy_fear_pct": _round(mean(r["peak_wealthy_fear"] for r in coverup_runs), 1),
            "day10_discontented_exhaustion_pct": _round(mean(r["day10_discontented_exhaustion"] for r in coverup_runs), 1),
            "coverup_scar": _round(mean(r["coverup_scar"] for r in coverup_runs)),
            "max_employer_cut_workers": _round(mean(r["max_employer_cut_workers"] for r in coverup_runs), 1),
        },
        "early_transparent_reform_arm": {
            "mean_trust": _round(mean(r["mean_trust"] for r in reform_runs)),
            "total_losses": _round(mean(r["total_losses"] for r in reform_runs)),
            "aftershock_rate": _round(mean(1.0 if r["aftershock_occurred"] else 0.0 for r in reform_runs)),
            "peak_wealthy_fear_pct": _round(mean(r["peak_wealthy_fear"] for r in reform_runs), 1),
            "day10_discontented_exhaustion_pct": _round(mean(r["day10_discontented_exhaustion"] for r in reform_runs), 1),
            "reform_credit": _round(mean(r["reform_credit"] for r in reform_runs)),
            "max_employer_cut_workers": _round(mean(r["max_employer_cut_workers"] for r in reform_runs), 1),
        },
    }


def exp4_power_aligned_defense_wall_breach():
    """Deney 4: İktidar yanlılarında savunma duvarı söylemle mi yoksa mutfak/işveren darbesiyle mi çatlar?"""
    def run_regime(mode):
        sim = Simulation(Config(population=100, seed=44))
        sim.run(0, BaselineProvider())
        pa = [a for a in sim.agents.values() if a.initial_group == "power_aligned"]
        leaders_a = [a.id for a in sim.agents.values() if a.initial_group == "authority" and a.alignment == "A"]
        wealthy_b = [a.id for a in sim.agents.values() if a.initial_group == "wealthy" and a.behavior.get("subwing") == "pro_B"]
        breach_day = None

        if mode in ("moderate_price_plus_lie", "severe_kitchen_and_employer_cut"):
            mult = 1.45 if mode == "moderate_price_plus_lie" else 2.15
            sim.schedule(30, "price_shock", {"multiplier": mult})

        for day in range(35):
            t0 = day * 1440 + 20
            if mode == "rhetoric_only" and wealthy_b:
                sim.schedule(t0, "external_action", {
                    "actor": wealthy_b[0],
                    "proposal": {"type": "amplify", "topic": "grievance", "claim": 95, "text": "Her şey çok kötü!"},
                })
            if mode in ("moderate_price_plus_lie", "severe_kitchen_and_employer_cut") and leaders_a and day % 5 == 0:
                la = leaders_a[0]
                for idx, ag in enumerate(pa[:15]):
                    if not sim.edge(la, ag.id):
                        sim.edges.append({"source": la, "target": ag.id, "type": "authority", "trust": 0.85, "latency": 10})
                    if idx < 3:
                        sim.schedule(t0 + idx, "external_action", {
                            "actor": la,
                            "proposal": {"type": "send", "target": ag.id, "topic": "economic_outlook", "claim": 0, "text": "Enflasyon sıfır."},
                        })
            if mode == "severe_kitchen_and_employer_cut":
                sim.protocol["active_boycott"] = 0.32
            sim.run((day + 1) * 1440 - 1, BaselineProvider())
            avg_wall = mean(a.behavior["psychology"]["defense_wall"] for a in pa)
            if breach_day is None and avg_wall < 0.45:
                breach_day = day + 1

        return {
            "breach_day_below_045": breach_day,
            "final_defense_wall": _round(mean(a.behavior["psychology"]["defense_wall"] for a in pa)),
            "final_comfort": _round(mean(a.behavior["psychology"]["comfort"] for a in pa)),
            "final_private_loyalty": _round(mean(a.private_loyalty for a in pa)),
            "disillusioned_below_05_ratio": _round(sum(1 for a in pa if a.private_loyalty < 0.5) / len(pa)),
            "switched_pole_count": sum(a.behavior.get("switch_count", 0) for a in pa),
        }

    return {
        "regime_4A_opposition_rhetoric_only": run_regime("rhetoric_only"),
        "regime_4B_moderate_price_and_forecast_lie": run_regime("moderate_price_plus_lie"),
        "regime_4C_severe_price_employer_cut_and_lie": run_regime("severe_kitchen_and_employer_cut"),
    }


def exp5_exhaustion_vs_solidarity_curve():
    """Deney 5: Yalnız bırakılan stres (Öğrenilmiş Çaresizlik) vs Dayanışmalı stres eğrisi (40 gün)."""
    def trace(collective_supported: bool):
        sim = Simulation(Config(population=100, seed=44))
        di = [a for a in sim.agents.values() if a.initial_group == "discontented"]
        checkpoints = {}
        for day in range(1, 41):
            for a in di:
                psychology.daily(
                    sim, a, harm=0.68, income_harm=0.35, disruption_level=0.40,
                    responsibility_own=0.5, max_own_error=0.25,
                    collective_supported=collective_supported,
                )
            if day in (1, 3, 7, 14, 25, 40):
                ps = [a.behavior["psychology"] for a in di]
                checkpoints[f"day_{day}"] = {
                    "anger": _round(mean(p["anger"] for p in ps)),
                    "exhaustion": _round(mean(p["exhaustion"] for p in ps)),
                    "effective_drive": _round(mean(p["effective_drive"] for p in ps)),
                }
        return checkpoints

    return {
        "isolated_no_solidarity": trace(False),
        "connected_local_solidarity": trace(True),
    }


def exp6_cumulative_institutional_memory():
    """Deney 6: Ardışık 4 örtbas krizinde kümülatif kurumsal hafıza ve sızıntı hızlanması."""
    sim = termux.create_pilot(seed=44)
    scenarios = [
        ("Kriz 1: İhale yolsuzluğu ve yayın yasağı", 7),
        ("Kriz 2: Maden ocağında göçük ve denetim ihmali", 8),
        ("Kriz 3: Fabrika yangını ve güvenlik açığı", 8),
        ("Kriz 4: Köprü çökmesi ve ihmal iddiası", 8),
    ]
    timeline = []
    for title, days in scenarios:
        ch = termux.init_scenario_chain(sim, title)
        leak_day = None
        for d in range(1, days + 1):
            termux.advance_scenario_day(sim, ReferenceAdvisor())
            if leak_day is None and ch["conditions"]["leak_occurred"]:
                leak_day = d
        opp = [a for a in sim.agents.values() if a.initial_group == "opposition"]
        di = [a for a in sim.agents.values() if a.initial_group == "discontented"]
        pa = [a for a in sim.agents.values() if a.initial_group == "power_aligned"]
        mem = psychology.institutional_memory_state(sim)
        timeline.append({
            "crisis": title,
            "past_crises_before_start": mem["past_crises"],
            "leak_erupted_on_day": leak_day,
            "opp_tolerance_threshold": _round(mean(a.behavior["psychology"]["tolerance_threshold"] for a in opp)),
            "discontented_tolerance_threshold": _round(mean(a.behavior["psychology"]["tolerance_threshold"] for a in di)),
            "power_aligned_defense_wall": _round(mean(a.behavior["psychology"]["defense_wall"] for a in pa)),
            "mean_trust": _round(sim.behavior_metrics()["mean_trust"]),
        })
    # Son krizi de hafızaya işle
    psychology.imprint_institutional_memory(sim, sim.protocol["termux_pilot"]["scenario_chain"])
    return {
        "final_memory": deepcopy(psychology.institutional_memory_state(sim)),
        "crisis_progression": timeline,
    }


def run_all_studies(output_path: Path | str = Path("reports/psychology-research-v34.json")) -> dict:
    v34_profile = behavior.load_v34_profile()
    results = {
        "study": "People1000 v3.4 Affective Psychology & Social Topology Empirical Research",
        "behavior_version": v34_profile["behavior_version"],
        "psychology_model": v34_profile["psychology_model"],
        "experiments": {
            "exp1_v33_vs_v34_and_1000_scale": exp1_v33_vs_v34_and_scale(),
            "exp2_preference_falsification_and_rebound": exp2_preference_falsification_and_rebound(),
            "exp3_coverup_vs_early_reform_branching": exp3_coverup_vs_early_reform_branching(),
            "exp4_power_aligned_defense_wall_breach": exp4_power_aligned_defense_wall_breach(),
            "exp5_exhaustion_vs_solidarity_curve": exp5_exhaustion_vs_solidarity_curve(),
            "exp6_cumulative_institutional_memory": exp6_cumulative_institutional_memory(),
        },
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    data = run_all_studies()
    print(json.dumps(data, ensure_ascii=False, indent=2))
