from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campus_pathfinding.domain.models import OptimizationProfile, UserPreferences, WeatherMode
from campus_pathfinding.services.planner import get_planner


OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    planner = get_planner()
    od_pairs = [
        ("mu_interior", "ladd_interior"),
        ("library_interior", "minard_interior"),
        ("wallman_interior", "sudro_interior"),
        ("mu_interior", "qbb_interior"),
    ]
    scenarios = ["clear_day", "rainy_evening", "winter_storm", "freezing_night"]
    profiles = [
        OptimizationProfile.BALANCED,
        OptimizationProfile.INDOOR_PREFERRED,
        OptimizationProfile.WINTER_SAFE,
        OptimizationProfile.WHEELCHAIR_ACCESSIBLE,
    ]

    rows: list[dict[str, object]] = []
    for scenario in scenarios:
        for profile in profiles:
            preferences = UserPreferences(optimization_profile=profile).normalized()
            for start, destination in od_pairs:
                recommendation = planner.plan_route(
                    start=start,
                    destination=destination,
                    departure_time=None,
                    weather_mode=WeatherMode.SCENARIO,
                    preferences=preferences,
                    scenario_name=scenario,
                )
                for result in recommendation.algorithm_comparison:
                    rows.append(
                        {
                            "scenario": scenario,
                            "profile": profile.value,
                            "start": recommendation.start,
                            "destination": recommendation.destination,
                            **{key: result[key] for key in ["algorithm", "total_cost", "distance_m", "outdoor_distance_m", "nodes_expanded", "runtime_ms"]},
                        }
                    )

    frame = pd.DataFrame(rows)
    output_path = OUTPUT_DIR / "algorithm_benchmark.csv"
    frame.to_csv(output_path, index=False)
    summary = frame.groupby(["scenario", "profile", "algorithm"], as_index=False).agg(
        avg_cost=("total_cost", "mean"),
        avg_outdoor_distance=("outdoor_distance_m", "mean"),
        avg_expanded=("nodes_expanded", "mean"),
        avg_runtime_ms=("runtime_ms", "mean"),
    )
    summary_path = OUTPUT_DIR / "algorithm_benchmark_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Wrote detailed benchmark results to {output_path}")
    print(f"Wrote benchmark summary to {summary_path}")


if __name__ == "__main__":
    main()
