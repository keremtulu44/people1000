"""Offline experiment runner. No API credentials or network access required."""
import argparse
import json
from pathlib import Path

from .engine import Config, Simulation


def main():
    parser = argparse.ArgumentParser(description="People1000 kapalı toplum deneyi")
    parser.add_argument("--population", type=int, default=100)
    parser.add_argument("--seed", type=int, default=44)
    parser.add_argument("--days", type=int, default=3, help="İlerletilecek gün sayısı")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--output", type=Path, default=Path("runs/demo.json"))
    parser.add_argument("--demo", action="store_true", help="Fiyat şoku ve sınırlı açıklama ekle")
    args = parser.parse_args()
    if args.days < 0:
        parser.error("--days negatif olamaz")
    sim = Simulation.load(args.resume) if args.resume else Simulation(Config(args.population, args.seed))
    sim.run(sim.time)  # Complete initial daily routine before interventions.
    if args.demo:
        sim.schedule(sim.time + 60, "price_shock", {"multiplier": 1.4})
        leader = next(iter(sim.authorities))
        target = next(e["target"] for e in sim.edges if e["source"] == leader)
        sim.apply(sim.propose(leader, {"type": "send", "target": target,
            "text": "Fiyat artışının geçici olduğunu düşünüyorum.", "topic": "power:A", "claim": 80}))
    sim.run(sim.time + args.days * 1440)
    sim.save(args.output)
    print(json.dumps(sim.metrics(), ensure_ascii=False, indent=2))
    print(f"Kayıt: {args.output}")


if __name__ == "__main__":
    main()
