from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from math import inf
from typing import Any

from pydantic import BaseModel, Field


class OptimizationProfile(str, Enum):
    BALANCED = "balanced"
    FASTEST = "fastest"
    INDOOR_PREFERRED = "indoor_preferred"
    WHEELCHAIR_ACCESSIBLE = "wheelchair_accessible"
    SAFEST_AT_NIGHT = "safest_at_night"
    WINTER_SAFE = "winter_safe"


class WeatherMode(str, Enum):
    SCENARIO = "scenario"
    LIVE = "live"


class BestMode(str, Enum):
    WALKING = "walking"
    TRANSIT = "transit"


@dataclass(slots=True)
class WeatherSnapshot:
    source: str
    condition: str
    temp_c: float
    feels_like_c: float
    wind_speed_mps: float
    rain_mm: float
    snow_mm: float
    wind_chill_c: float
    is_night: bool = False

    def severity_index(self) -> float:
        cold_term = max(0.0, -self.wind_chill_c) / 10.0
        wind_term = self.wind_speed_mps / 6.0
        precip_term = (self.rain_mm * 0.5) + self.snow_mm
        return cold_term + wind_term + precip_term


@dataclass(slots=True)
class UserPreferences:
    optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    wheelchair_required: bool = False
    avoid_stairs: bool = False
    prefer_indoor: bool = False
    prefer_well_lit: bool = False
    winter_safety_mode: bool = False
    allow_transit: bool = False
    prefer_transit: bool = False
    max_transfers: int = 1
    crowd_avoidance: float = 0.5

    def normalized(self) -> "UserPreferences":
        profile = self.optimization_profile
        return UserPreferences(
            optimization_profile=profile,
            wheelchair_required=self.wheelchair_required or profile == OptimizationProfile.WHEELCHAIR_ACCESSIBLE,
            avoid_stairs=self.avoid_stairs or profile in {OptimizationProfile.WHEELCHAIR_ACCESSIBLE, OptimizationProfile.WINTER_SAFE},
            prefer_indoor=self.prefer_indoor or profile in {OptimizationProfile.INDOOR_PREFERRED, OptimizationProfile.WINTER_SAFE},
            prefer_well_lit=self.prefer_well_lit or profile == OptimizationProfile.SAFEST_AT_NIGHT,
            winter_safety_mode=self.winter_safety_mode or profile == OptimizationProfile.WINTER_SAFE,
            allow_transit=self.allow_transit,
            prefer_transit=self.prefer_transit,
            max_transfers=self.max_transfers,
            crowd_avoidance=self.crowd_avoidance,
        )


@dataclass(slots=True)
class EdgeCostBreakdown:
    distance: float
    weather_penalty: float
    accessibility_penalty: float
    safety_penalty: float
    crowd_penalty: float
    total_cost: float
    blockers: list[str] = field(default_factory=list)

    @property
    def is_feasible(self) -> bool:
        return self.total_cost < inf

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["total_cost"] == inf:
            payload["total_cost"] = None
        return payload


@dataclass(slots=True)
class AlgorithmRun:
    algorithm: str
    mode: str
    path: list[str]
    path_names: list[str]
    total_cost: float
    distance_m: float
    indoor_distance_m: float
    outdoor_distance_m: float
    weather_penalty: float
    accessibility_penalty: float
    safety_penalty: float
    crowd_penalty: float
    nodes_expanded: int
    runtime_ms: float
    explanation: str
    edge_breakdowns: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransitLeg:
    route_id: str
    route_short_name: str
    route_long_name: str
    board_stop_id: str
    board_stop_name: str
    alight_stop_id: str
    alight_stop_name: str
    departure_time: str
    arrival_time: str
    wait_minutes: float
    ride_minutes: float


@dataclass(slots=True)
class TransitRecommendation:
    mode: str
    total_cost: float
    estimated_duration_min: float
    walking_distance_m: float
    walking_time_min: float
    wait_time_min: float
    in_vehicle_time_min: float
    transfers: int
    route_summary: str
    explanation: str
    live_data_used: bool
    path_names: list[str]
    legs: list[TransitLeg]


@dataclass(slots=True)
class RouteRecommendation:
    requested_at: str
    start: str
    destination: str
    departure_time: str
    weather: dict[str, Any]
    preferences: dict[str, Any]
    best_mode: str
    recommended_route: AlgorithmRun
    alternative_route: AlgorithmRun | None
    transit_option: TransitRecommendation | None
    algorithm_comparison: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


class RouteRequestModel(BaseModel):
    start: str = Field(..., description="Node identifier for the origin.")
    destination: str = Field(..., description="Node identifier for the destination.")
    departure_time: datetime | None = Field(default=None, description="Requested travel time.")
    weather_mode: WeatherMode = WeatherMode.SCENARIO
    scenario_name: str | None = None
    optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    wheelchair_required: bool = False
    avoid_stairs: bool = False
    prefer_indoor: bool = False
    prefer_well_lit: bool = False
    winter_safety_mode: bool = False
    allow_transit: bool = False
    prefer_transit: bool = False
    max_transfers: int = Field(default=1, ge=0, le=2)
    crowd_avoidance: float = Field(default=0.5, ge=0.0, le=1.0)


class LocationModel(BaseModel):
    node_id: str
    name: str
    description: str
    open_time: str
    close_time: str


class ScenarioModel(BaseModel):
    key: str
    label: str
    description: str
    condition: str
    temp_c: float
    wind_speed_mps: float
    snow_mm: float
    rain_mm: float
    wind_chill_c: float
    is_night: bool


def preferences_from_request(request: RouteRequestModel) -> UserPreferences:
    return UserPreferences(
        optimization_profile=request.optimization_profile,
        wheelchair_required=request.wheelchair_required,
        avoid_stairs=request.avoid_stairs,
        prefer_indoor=request.prefer_indoor,
        prefer_well_lit=request.prefer_well_lit,
        winter_safety_mode=request.winter_safety_mode,
        allow_transit=request.allow_transit,
        prefer_transit=request.prefer_transit,
        max_transfers=request.max_transfers,
        crowd_avoidance=request.crowd_avoidance,
    ).normalized()
