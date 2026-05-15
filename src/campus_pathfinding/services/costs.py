from __future__ import annotations

from datetime import datetime, time
from math import inf
from typing import Any

from campus_pathfinding.domain.models import EdgeCostBreakdown, OptimizationProfile, UserPreferences, WeatherSnapshot


def _parse_time(value: str) -> time | None:
    if value == "always":
        return None
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


def _is_open(open_time: str, close_time: str, departure_time: datetime) -> bool:
    if open_time == "always" and close_time == "always":
        return True
    start = _parse_time(open_time)
    end = _parse_time(close_time)
    if start is None or end is None:
        return True
    current = departure_time.time()
    return start <= current <= end


def _crowd_multiplier(crowd_level: str, departure_time: datetime) -> float:
    rush_hours = {9, 10, 11, 12, 13, 14}
    evening_hours = {17, 18}
    base = {"low": 4.0, "medium": 10.0, "high": 18.0}.get(crowd_level, 8.0)
    if departure_time.hour in rush_hours:
        return base * 1.4
    if departure_time.hour in evening_hours:
        return base * 1.1
    return base


class DynamicCostEngine:
    """Computes dynamic edge costs under weather, safety, and accessibility constraints."""

    def __init__(self) -> None:
        self.profile_multipliers = {
            OptimizationProfile.BALANCED: {"weather": 1.0, "accessibility": 1.0, "safety": 1.0, "crowd": 1.0},
            OptimizationProfile.FASTEST: {"weather": 0.7, "accessibility": 0.8, "safety": 0.6, "crowd": 0.5},
            OptimizationProfile.INDOOR_PREFERRED: {"weather": 1.4, "accessibility": 1.0, "safety": 0.9, "crowd": 1.0},
            OptimizationProfile.WHEELCHAIR_ACCESSIBLE: {"weather": 1.0, "accessibility": 1.5, "safety": 1.0, "crowd": 0.9},
            OptimizationProfile.SAFEST_AT_NIGHT: {"weather": 0.9, "accessibility": 1.0, "safety": 1.6, "crowd": 0.8},
            OptimizationProfile.WINTER_SAFE: {"weather": 1.7, "accessibility": 1.2, "safety": 1.3, "crowd": 0.8},
        }

    def edge_cost(
        self,
        edge: dict[str, Any],
        source_node: dict[str, Any],
        target_node: dict[str, Any],
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
    ) -> EdgeCostBreakdown:
        blockers: list[str] = []
        profile_weights = self.profile_multipliers[preferences.optimization_profile]

        if not _is_open(edge["open_time"], edge["close_time"], departure_time):
            blockers.append("edge_closed")
        if source_node["is_indoor"] and not _is_open(source_node["open_time"], source_node["close_time"], departure_time):
            blockers.append(f"{source_node['name']}_closed")
        if target_node["is_indoor"] and not _is_open(target_node["open_time"], target_node["close_time"], departure_time):
            blockers.append(f"{target_node['name']}_closed")

        if blockers:
            return EdgeCostBreakdown(
                distance=float(edge["distance_m"]),
                weather_penalty=0.0,
                accessibility_penalty=0.0,
                safety_penalty=0.0,
                crowd_penalty=0.0,
                total_cost=inf,
                blockers=blockers,
            )

        accessibility_penalty = 0.0
        if preferences.wheelchair_required and not edge["is_accessible"]:
            return EdgeCostBreakdown(
                distance=float(edge["distance_m"]),
                weather_penalty=0.0,
                accessibility_penalty=inf,
                safety_penalty=0.0,
                crowd_penalty=0.0,
                total_cost=inf,
                blockers=["not_wheelchair_accessible"],
            )
        if preferences.wheelchair_required and edge["has_stairs"]:
            return EdgeCostBreakdown(
                distance=float(edge["distance_m"]),
                weather_penalty=0.0,
                accessibility_penalty=inf,
                safety_penalty=0.0,
                crowd_penalty=0.0,
                total_cost=inf,
                blockers=["stairs_block_wheelchair"],
            )
        if preferences.avoid_stairs and edge["has_stairs"]:
            accessibility_penalty += 45.0
        if not edge["is_accessible"]:
            accessibility_penalty += 15.0

        weather_penalty = 0.0
        if edge["is_weather_exposed"]:
            precip_penalty = (weather.snow_mm * 8.0) + (weather.rain_mm * 4.5)
            wind_penalty = max(0.0, weather.wind_speed_mps - 4.0) * 2.0
            cold_penalty = max(0.0, -weather.wind_chill_c - 5.0) * 1.3
            weather_penalty += precip_penalty + wind_penalty + cold_penalty
            if preferences.prefer_indoor:
                weather_penalty += 20.0
            if preferences.winter_safety_mode:
                weather_penalty += 25.0
        elif edge["is_tunnel"] or edge["is_skyway"] or edge["is_indoor"]:
            weather_penalty += max(0.0, weather.snow_mm - 2.0) * 0.5

        safety_penalty = 0.0
        if weather.is_night and not edge["well_lit"]:
            safety_penalty += 35.0
        if preferences.prefer_well_lit and not edge["well_lit"]:
            safety_penalty += 28.0
        if preferences.winter_safety_mode and edge["has_stairs"]:
            safety_penalty += 20.0

        crowd_penalty = _crowd_multiplier(str(edge["crowd_level"]), departure_time) * preferences.crowd_avoidance

        weather_penalty *= profile_weights["weather"]
        accessibility_penalty *= profile_weights["accessibility"]
        safety_penalty *= profile_weights["safety"]
        crowd_penalty *= profile_weights["crowd"]

        total_cost = (
            float(edge["distance_m"])
            + weather_penalty
            + accessibility_penalty
            + safety_penalty
            + crowd_penalty
        )

        return EdgeCostBreakdown(
            distance=float(edge["distance_m"]),
            weather_penalty=weather_penalty,
            accessibility_penalty=accessibility_penalty,
            safety_penalty=safety_penalty,
            crowd_penalty=crowd_penalty,
            total_cost=total_cost,
            blockers=blockers,
        )
