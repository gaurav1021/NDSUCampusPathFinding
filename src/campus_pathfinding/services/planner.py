from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from typing import Any

from campus_pathfinding.config import get_settings
from campus_pathfinding.data.loader import load_edges, load_frame, load_nodes, load_scenarios
from campus_pathfinding.domain.models import (
    BestMode,
    LocationModel,
    RouteRecommendation,
    ScenarioModel,
    UserPreferences,
    WeatherMode,
    WeatherSnapshot,
)
from campus_pathfinding.services.costs import DynamicCostEngine
from campus_pathfinding.services.explainer import RouteExplainer
from campus_pathfinding.services.gtfs import MatbusStaticFeed
from campus_pathfinding.services.graph_builder import CampusGraphBuilder
from campus_pathfinding.services.router import CampusRouter
from campus_pathfinding.services.transit import MatbusTransitService
from campus_pathfinding.services.weather import WeatherService


class CampusPlanner:
    def __init__(self) -> None:
        settings = get_settings()
        nodes_frame = load_nodes(settings.nodes_path)
        edges_frame = load_edges(settings.edges_path)
        scenarios = load_scenarios(settings.scenarios_path)
        stop_links = load_frame(settings.matbus_stop_links_path)

        graph_bundle = CampusGraphBuilder().build(nodes_frame, edges_frame)
        static_feed = MatbusStaticFeed.from_directory(settings.matbus_gtfs_dir) if settings.matbus_gtfs_dir.exists() else None
        self.settings = settings
        self.scenarios = scenarios
        self.weather_service = WeatherService(settings, scenarios)
        self.router = CampusRouter(graph_bundle.graph, DynamicCostEngine(), RouteExplainer())
        self.transit_service = MatbusTransitService(settings, graph_bundle.graph, stop_links, static_feed)
        self.nodes_frame = graph_bundle.nodes_frame
        self.edges_frame = graph_bundle.edges_frame
        self.graph = graph_bundle.graph

    def get_locations(self) -> list[LocationModel]:
        selectable = self.nodes_frame[self.nodes_frame["selectable"]]
        return [
            LocationModel(
                node_id=row["node_id"],
                name=row["name"],
                description=row["description"],
                open_time=row["open_time"],
                close_time=row["close_time"],
            )
            for row in selectable.to_dict(orient="records")
        ]

    def get_scenarios(self) -> list[ScenarioModel]:
        payload: list[ScenarioModel] = []
        for key, scenario in self.scenarios.items():
            payload.append(
                ScenarioModel(
                    key=key,
                    label=scenario["label"],
                    description=scenario["description"],
                    condition=scenario["condition"],
                    temp_c=scenario["temp_c"],
                    wind_speed_mps=scenario["wind_speed_mps"],
                    snow_mm=scenario["snow_mm"],
                    rain_mm=scenario["rain_mm"],
                    wind_chill_c=scenario["wind_chill_c"],
                    is_night=scenario["is_night"],
                )
            )
        return payload

    def resolve_weather(self, weather_mode: WeatherMode, scenario_name: str | None = None) -> WeatherSnapshot:
        if weather_mode == WeatherMode.LIVE:
            return self.weather_service.get_live_weather()
        selected = scenario_name or self.settings.default_scenario
        return self.weather_service.get_scenario_weather(selected)

    def plan_route(
        self,
        start: str,
        destination: str,
        departure_time: datetime | None,
        weather_mode: WeatherMode,
        preferences: UserPreferences,
        scenario_name: str | None = None,
    ) -> RouteRecommendation:
        departure = departure_time or datetime.now()
        weather = self.resolve_weather(weather_mode, scenario_name)
        primary = self.router.run_a_star(start, destination, departure, weather, preferences)
        alternative = self.router.find_alternative_route(start, destination, departure, weather, preferences, primary.path)
        comparison = self.router.compare_algorithms(start, destination, departure, weather, preferences)
        transit_option = self.transit_service.find_transit_option(start, destination, departure, preferences)
        best_mode = BestMode.WALKING.value
        if transit_option:
            walking_bias = 60.0 if preferences.prefer_transit else 0.0
            if (transit_option.total_cost - walking_bias) < primary.total_cost:
                best_mode = BestMode.TRANSIT.value

        return RouteRecommendation(
            requested_at=datetime.now().isoformat(timespec="seconds"),
            start=self.graph.nodes[start]["name"],
            destination=self.graph.nodes[destination]["name"],
            departure_time=departure.isoformat(timespec="minutes"),
            weather=asdict(weather),
            preferences=asdict(preferences),
            best_mode=best_mode,
            recommended_route=primary,
            alternative_route=alternative,
            transit_option=transit_option,
            algorithm_comparison=comparison,
        )

    def graph_payload(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes_frame.to_dict(orient="records"),
            "edges": self.edges_frame.to_dict(orient="records"),
            "transit_enabled": self.transit_service.has_static_feed(),
        }


@lru_cache(maxsize=1)
def get_planner() -> CampusPlanner:
    return CampusPlanner()
