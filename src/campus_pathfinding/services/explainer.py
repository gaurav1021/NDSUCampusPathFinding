from __future__ import annotations

from campus_pathfinding.domain.models import AlgorithmRun, UserPreferences, WeatherSnapshot


class RouteExplainer:
    def explain(self, result: AlgorithmRun, weather: WeatherSnapshot, preferences: UserPreferences) -> str:
        if not result.path_names:
            return "No feasible route was found under the requested constraints."

        route_type = "mixed indoor-outdoor"
        if result.outdoor_distance_m == 0:
            route_type = "fully indoor"
        elif result.indoor_distance_m == 0:
            route_type = "fully outdoor"

        reasons: list[str] = [
            f"The selected path is a {route_type} route with {result.distance_m:.0f} meters of walking."
        ]

        if preferences.prefer_indoor or preferences.winter_safety_mode:
            reasons.append(
                f"It limits outdoor exposure to {result.outdoor_distance_m:.0f} meters under {weather.condition} conditions."
            )
        if preferences.wheelchair_required:
            reasons.append("All traversed edges satisfy the wheelchair-accessibility requirement.")
        if weather.is_night or preferences.prefer_well_lit:
            reasons.append("The route minimizes poorly lit segments when nighttime safety is important.")
        if result.crowd_penalty > 0:
            reasons.append("Congestion-aware costs also helped avoid the busiest campus spine segments where possible.")

        return " ".join(reasons)
