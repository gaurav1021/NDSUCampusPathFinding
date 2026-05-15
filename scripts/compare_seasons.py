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
    preferences = UserPreferences(optimization_profile=OptimizationProfile.WINTER_SAFE).normalized()
    pairs = [
        ("mu_interior", "ladd_interior"),
        ("mu_interior", "sudro_interior"),
        ("wallman_interior", "minard_interior"),
        ("library_interior", "qbb_interior"),
    ]

    rows: list[dict[str, object]] = []
    for start, destination in pairs:
        summer = planner.plan_route(start, destination, None, WeatherMode.SCENARIO, preferences, "clear_day")
        winter = planner.plan_route(start, destination, None, WeatherMode.SCENARIO, preferences, "winter_storm")
        rows.append(
            {
                "start": summer.start,
                "destination": summer.destination,
                "summer_path": " -> ".join(summer.recommended_route.path_names),
                "winter_path": " -> ".join(winter.recommended_route.path_names),
                "summer_cost": summer.recommended_route.total_cost,
                "winter_cost": winter.recommended_route.total_cost,
                "summer_outdoor_distance_m": summer.recommended_route.outdoor_distance_m,
                "winter_outdoor_distance_m": winter.recommended_route.outdoor_distance_m,
            }
        )

    frame = pd.DataFrame(rows)
    output_path = OUTPUT_DIR / "seasonal_route_comparison.csv"
    frame.to_csv(output_path, index=False)
    print(frame.to_string(index=False))
    print(f"\nWrote seasonal comparison to {output_path}")


if __name__ == "__main__":
    main()
